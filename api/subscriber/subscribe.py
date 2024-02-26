from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1
from api.analysis.models import AnalysisJob
from api.util.util import generate_stock_fair_value
from api.record.models import Record
import yfinance as yf
import logging
import json
import os

with open(
    os.path.dirname(os.path.dirname(__file__)) + "/config/gcp_config.json"
) as gcp_config_json:
    gcp_config = json.load(gcp_config_json)
GCP_PROJECT_ID = gcp_config["GCP_PROJECT_ID"]
PUB_SUB_SUBSCRIPTION = gcp_config["PUB_SUB_SUBSCRIPTION"]

subscriber = pubsub_v1.SubscriberClient()
subscription_path = subscriber.subscription_path(GCP_PROJECT_ID, PUB_SUB_SUBSCRIPTION)


def callback(message: pubsub_v1.subscriber.message.Message) -> None:
    stock_symbol = json.loads(message.data)["StockSymbol"]
    logging.info(f"Received Pub Sub message with for stock {stock_symbol}.")
    try:
        data = yf.Ticker(stock_symbol)
        df = data.history(period="1mo")
        most_recent_close = df.tail(1)["Close"].values[0]
        logging.info(
            f"Most recent close for stock {stock_symbol} is {most_recent_close}"
        )
        most_recent_fear_greed_index = int(Record.get_most_recent_record()["index"])
        AnalysisJob.update_analysis_job_by_id(
            analysis_job_id=json.loads(message.data)["JobId"],
            data={
                "fair_value": generate_stock_fair_value(
                    most_recent_close, most_recent_fear_greed_index
                )
            },
        )
        logging.info(f"Update analysis job for stock {stock_symbol} complete!")
        message.ack()
    except Exception as e:
        logging.error(
            f"Update analysis job for stock {json.loads(message.data)['StockSymbol']} failed! - {e}"
        )


streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
logging.info(f"Listening to Pub Sub subscription: {subscription_path}...")


def streaming_pull_pub_sub_subscription():
    with subscriber:
        try:
            streaming_pull_future.result(timeout=None)
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
        except TimeoutError:
            streaming_pull_future.cancel()
            streaming_pull_future.result()
