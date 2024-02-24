from flask import Blueprint, jsonify, request
from api.db.setup import db
import os
import logging
import json
import yfinance as yf
from google.cloud import pubsub_v1
from api.auth.auth import auth_required
from api.util.util import generate_response
from api.exception.models import BadRequestException
from api.analysis.models import AnalysisJob


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
        most_recent_fear_greed_index = int(
            list(db["records"].find().sort("created", -1).limit(0))[0]["index"]
        )
        fair_value = round(
            most_recent_close * ((100 - most_recent_fear_greed_index) / 100), 2
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
        return jsonify({"messageId": message_id}), 200
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
