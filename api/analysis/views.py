from flask import Blueprint, jsonify, request
from api.db.setup import db
from bson.objectid import ObjectId
import os
import logging
import json
import yfinance as yf
from google.cloud import pubsub_v1
from api.auth.auth import auth_required
from api.util.util import generate_response, generate_stock_fair_value
from api.exception.models import BadRequestException
from api.analysis.models import AnalysisJob
from api.record.models import Record


bp = Blueprint("analysis", __name__)

with open(
    os.path.dirname(os.path.dirname(__file__)) + "/config/gcp_config.json"
) as gcp_config_json:
    gcp_config = json.load(gcp_config_json)
GCP_PROJECT_ID = gcp_config["GCP_PROJECT_ID"]
PUB_SUB_TOPIC = gcp_config["PUB_SUB_TOPIC"]


topic_name = f"projects/{GCP_PROJECT_ID}/topics/{PUB_SUB_TOPIC}"


@bp.route("/analysis", methods=(["GET"]))
@auth_required
def get_stock_analysis(_):
    stock_symbol = request.args.get("stock", default=None, type=None)
    if not stock_symbol:
        raise BadRequestException("Provide a stock symbol", status_code=400)
    logging.info(f"Analysing stock with ticker symbol {stock_symbol}...")
    try:
        data = yf.Ticker(stock_symbol)
        df = data.history(period="1mo")
        most_recent_close = df.tail(1)["Close"].values[0]
        most_recent_close = float("{:.2f}".format(most_recent_close))
        most_recent_fear_greed_index = int(Record.get_most_recent_record()["index"])
        fair_value = generate_stock_fair_value(
            most_recent_close, most_recent_fear_greed_index
        )
        return (
            jsonify(
                {
                    "stock": stock_symbol,
                    "close": most_recent_close,
                    "mostRecentFearGreedIndex": most_recent_fear_greed_index,
                    "fairValue": fair_value,
                }
            ),
            200,
        )
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Get stock analysis failed"}), 500


@bp.route("/analysis-jobs", methods=(["POST"]))
@auth_required
def create_analysis_job(_):
    data = request.get_json()
    new_analysis_job = AnalysisJob(stock_symbol=data["stock"])
    try:
        analysis_job_id = new_analysis_job.save_analysis_job_to_db()
        logging.info(f"Created analysis job with id: {analysis_job_id}")
    except Exception as e:
        logging.error(e)
        return jsonify({"errors": [{"message": "Failed to create analysis job"}]}), 500
    try:
        publisher = pubsub_v1.PublisherClient()
        job_data_dict = {"StockSymbol": data["stock"], "JobId": str(analysis_job_id)}
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
    try:
        users = list(db["analysis_jobs"].find())
        return generate_response(users)
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
        stock_symbol = json.loads(pubsub_message["data"])["StockSymbol"]
        logging.info(f"Received Pub Sub message with for stock {stock_symbol}.")

    return ("", 204)
