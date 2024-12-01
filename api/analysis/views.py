from flask import Blueprint, jsonify, request
from api.db.setup import db
from bson.objectid import ObjectId
from concurrent.futures import ProcessPoolExecutor
from pydantic import BaseModel, ValidationError, field_validator, ValidationInfo
import time
import os
import base64
import logging
import json
import yfinance as yf
import pytz
import matplotlib
import matplotlib.pyplot as plt
import math
from google.cloud import storage
import io
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from google.cloud import pubsub_v1
from api.auth.auth import auth_required
from api.common.constants import ANALYSIS_JOB_CREATION_DAILY_LIMIT
from api.util.util import generate_response, generate_stock_fair_value, return_delta
from api.exception.models import BadRequestException
from api.analysis.models import AnalysisJob
from api.record.models import Record

matplotlib.use("agg")

bp = Blueprint("analysis", __name__)

with open(
    os.path.dirname(os.path.dirname(__file__)) + "/config/gcp_config.json"
) as gcp_config_json:
    gcp_config = json.load(gcp_config_json)
GCP_PROJECT_ID = gcp_config["GCP_PROJECT_ID"]
PUB_SUB_TOPIC = gcp_config["PUB_SUB_TOPIC"]
ASSET_BUCKET_NAME = gcp_config["ASSET_BUCKET_NAME"]

topic_name = f"projects/{GCP_PROJECT_ID}/topics/{PUB_SUB_TOPIC}"


class AnalysisJobRequest(BaseModel):
    stock: str
    targetFearGreedIndex: int
    targetPeRatio: int

    @field_validator("targetFearGreedIndex", "targetPeRatio")
    @classmethod
    def check_alphanumeric(cls, v: int, info: ValidationInfo) -> str:
        if v < 1 or v > 99:
            raise ValueError(f"{info.field_name} must be between 1 and 99 inclusive")
        return v


@bp.route("/analysis", methods=(["GET"]))
@auth_required
def get_stock_analysis(_):
    stock_symbol = request.args.get("stock", default=None, type=None)
    target_fear_greed_index = request.args.get(
        "targetFearGreedIndex", default=None, type=int
    )
    target_pe_ratio = request.args.get("targetPeRatio", default=None, type=float)

    if not stock_symbol:
        raise BadRequestException("Provide a stock symbol", status_code=400)
    logging.info(f"Analysing stock with ticker symbol {stock_symbol}...")
    try:
        data = yf.Ticker(stock_symbol)
        stock_info = data.info
        current_price = stock_info["currentPrice"]
        EPS = stock_info["trailingEps"]
        PE_ratio = float("{:.2f}".format(current_price / EPS))
        logging.info(f"{stock_symbol} has PE ratio of {PE_ratio}")
        df = data.history(period="1mo")

        for index, row in df.tail().iterrows():
            logging.info(f"Most recent close with index {index} is {row.Close}")

        most_recent_close = df.tail(1)["Close"].values[0]
        most_recent_close = float("{:.2f}".format(most_recent_close))
        most_recent_fear_greed_index = int(Record.get_most_recent_record()["index"])
        with ProcessPoolExecutor(1) as exe:
            future = exe.submit(
                generate_stock_fair_value,
                most_recent_close,
                most_recent_fear_greed_index,
                PE_ratio,
                target_fear_greed_index=target_fear_greed_index,
                target_pe_ratio=target_pe_ratio,
            )
            fair_value = future.result()
        return (
            jsonify(
                {
                    "stock": stock_symbol,
                    "close": most_recent_close,
                    "mostRecentFearGreedIndex": most_recent_fear_greed_index,
                    "fairValue": fair_value,
                    "delta": return_delta(fair_value, most_recent_close),
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get stock analysis failed"}), 500


@bp.route("/analysis-jobs/<analysis_id>", methods=["DELETE"])
@auth_required
def delete_alert_by_id(_, analysis_id):
    try:
        res = db["analysis_jobs"].delete_one({"_id": ObjectId(analysis_id)})
        if res.deleted_count:
            return jsonify({"message": "Analysis job deleted"}), 200

        else:
            return jsonify({"message": "Analysis job not found"}), 404
    except Exception:
        return jsonify({"message": "Delete alert by ID failed"}), 500


@bp.route("/analysis-jobs", methods=(["POST"]))
@auth_required
def create_analysis_job(user):
    data = request.get_json()
    current_user_analysis_jobs_past_one_day = (
        AnalysisJob.get_analysis_jobs_by_created_by_within_hours(user["_id"])
    )
    logging.info(
        f"Current user has created {len(current_user_analysis_jobs_past_one_day)} analysis jobs past 24 hours."
    )

    if (
        len(current_user_analysis_jobs_past_one_day)
        >= ANALYSIS_JOB_CREATION_DAILY_LIMIT
    ):
        return (
            jsonify(
                {
                    "errors": [
                        {
                            "message": f"User cannot create more than {ANALYSIS_JOB_CREATION_DAILY_LIMIT} analysis jobs every 24 hours!"
                        }
                    ]
                }
            ),
            500,
        )
    try:
        analysis_job_request = AnalysisJobRequest.model_validate_json(request.data)
        new_analysis_job = AnalysisJob(
            stock_symbol=analysis_job_request.stock,
            target_fear_greed_index=analysis_job_request.targetFearGreedIndex,
            target_pe_ratio=analysis_job_request.targetFearGreedIndex,
            created_by=user["_id"],
        )
        analysis_job_id = new_analysis_job.save_analysis_job_to_db()
        logging.info(f"Created analysis job with id: {analysis_job_id}")
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(e)
        return jsonify({"errors": [{"message": "Failed to create analysis job"}]}), 500
    try:
        publisher = pubsub_v1.PublisherClient()
        job_data_dict = {
            "StockSymbol": data["stock"],
            "TargetFearGreedIndex": data["targetFearGreedIndex"],
            "TargetPeRatio": data["targetPeRatio"],
            "JobId": str(analysis_job_id),
        }
        job_data_encode = json.dumps(job_data_dict, indent=2).encode("utf-8")
        future = publisher.publish(topic_name, job_data_encode)
        message_id = future.result()
        return (
            jsonify({"messageId": message_id, "analysisJobId": str(analysis_job_id)}),
            200,
        )
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Create analysis job failed"}), 500


@bp.route("/analysis-jobs", methods=(["GET"]))
@auth_required
def get_analysis_jobs(_):
    page_size = int(request.args["pageSize"]) if "pageSize" in request.args else 10
    current_page = int(request.args["page"]) if "page" in request.args else 1
    try:
        total_records = db["analysis_jobs"].estimated_document_count()
        total_pages = math.ceil(total_records / page_size)
        if current_page > total_pages:
            return (
                jsonify(
                    {
                        "errors": [
                            {
                                "message": f"Requested page {current_page} exceeds max page size"
                            }
                        ]
                    }
                ),
                400,
            )
        analysis_jobs = list(
            db["analysis_jobs"]
            .find()
            .sort("created", -1)
            .skip((current_page - 1) * page_size)
            .limit(page_size)
        )

        return generate_response(
            {
                "paginationMetadata": {
                    "totalRecords": total_records,
                    "currentPage": current_page,
                    "totalPages": total_pages,
                },
                "analysisJobs": analysis_jobs,
            }
        )

    except Exception as e:
        logging.error(e)
        return jsonify({"errors": [{"message": "Get analysis jobs failed"}]}), 500


@bp.route("/analysis-jobs/<analysis_job_id>", methods=(["GET"]))
def get_analysis_jobs_by_id(analysis_job_id):
    try:
        analysis_job = db["analysis_jobs"].find_one({"_id": ObjectId(analysis_job_id)})
        if analysis_job:
            return generate_response(analysis_job)
        else:
            return "Analysis job not found", 404
    except Exception:
        return jsonify({"message": "Get analysis job by ID failed"}), 500


@bp.route("/subscription-push", methods=(["POST"]))
def handle_pubsub_subscription_push():
    envelope = request.get_json()
    if not envelope:
        msg = "no Pub/Sub message received"
        logging.error(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    if not isinstance(envelope, dict) or "message" not in envelope:
        msg = "invalid Pub/Sub message format"
        logging.error(f"error: {msg}")
        return f"Bad Request: {msg}", 400

    pubsub_message = envelope["message"]

    if isinstance(pubsub_message, dict) and "data" in pubsub_message:
        message_string = (
            base64.b64decode(pubsub_message["data"]).decode("utf-8").strip()
        )
        message_json = json.loads(message_string)
        stock_symbol = message_json["StockSymbol"]
        target_fear_greed_index = message_json["TargetFearGreedIndex"]
        target_pe_ratio = message_json["TargetPeRatio"]
        job_id = message_json["JobId"]
        logging.info(
            f"Received Pub Sub message with for stock {stock_symbol} with job ID {job_id}; {target_fear_greed_index} and {target_pe_ratio}"
        )
        try:
            start_time = time.perf_counter()
            data = yf.Ticker(stock_symbol)
            df = data.history(period="1mo")
            stock_info = data.info
            current_price = stock_info["currentPrice"]
            EPS = stock_info["trailingEps"]
            PE_ratio = float("{:.2f}".format(current_price / EPS))
            logging.info(f"{stock_symbol} has PE ratio of {PE_ratio}")
            most_recent_close = df.tail(1)["Close"].values[0]
            logging.info(
                f"Most recent close for stock {stock_symbol} is {most_recent_close}"
            )
            most_recent_fear_greed_index = int(Record.get_most_recent_record()["index"])
            fair_value = generate_stock_fair_value(
                most_recent_close,
                most_recent_fear_greed_index,
                PE_ratio,
                target_fear_greed_index=target_fear_greed_index,
                target_pe_ratio=target_pe_ratio,
            )
            AnalysisJob.update_analysis_job_by_id(
                analysis_job_id=job_id,
                data={
                    "most_recent_fear_greed_index": most_recent_fear_greed_index,
                    "current_pe_ratio": PE_ratio,
                    "target_fear_greed_index": target_fear_greed_index,
                    "target_pe_ratio": target_pe_ratio,
                    "fair_value": fair_value,
                    "delta": return_delta(fair_value, most_recent_close),
                    "complete": True,
                },
            )
            logging.info(f"Update analysis job for stock {stock_symbol} complete!")
        except Exception as e:
            logging.error(f"Update analysis job failed -  {e}")
        finally:
            end_time = time.perf_counter()
            formatted_time_taken = "{:.2f}".format(round(end_time - start_time, 2))
            logging.info(f"Time taken: {formatted_time_taken}")

    return ("", 204)


@bp.route("/generate-stock-plot", methods=(["POST"]))
@auth_required
def generate_stock_plot_gcs_blob(_):
    stock_symbol = request.args.get("stock", default=None, type=None)
    target_price = request.args.get("targetPrice", default=None, type=None)

    if not stock_symbol:
        raise BadRequestException("Provide a stock symbol", status_code=400)

    today = datetime.today()
    one_year_ago = today - relativedelta(years=1)
    formatted_date = one_year_ago.strftime("%Y-%m-%d")
    data = yf.download([stock_symbol], formatted_date)["Close"]

    y_label = "Close Value"
    data.plot(figsize=(10, 6))

    if target_price:
        plt.axhline(
            y=int(target_price),
            color="r",
            linestyle="--",
            label=f"Target Price: ${target_price}",
        )

    plt.legend()
    plt.title("Stock Charts Plot", fontsize=16)

    # Define the labels
    plt.ylabel(y_label, fontsize=14)
    plt.xlabel("Time", fontsize=14)

    # Plot the grid lines
    plt.grid(which="major", color="k", linestyle="-.", linewidth=0.5)

    fig_to_upload = plt.gcf()

    buf = io.BytesIO()
    fig_to_upload.savefig(buf, format="png")

    storage_client = storage.Client()
    bucket = storage_client.bucket(ASSET_BUCKET_NAME)
    GB = pytz.timezone("Europe/London")
    timestamp = datetime.now(timezone.utc).astimezone(GB).timestamp()
    blob = bucket.blob(f"{timestamp}-{stock_symbol}-plot.png")
    blob.upload_from_file(buf, content_type="image/png", rewind=True)
    return jsonify({"image_url": blob.public_url}), 200
