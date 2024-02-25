from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1
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
    logging.info(
        f"Received Pub Sub message with for stock {json.loads(message.data)['StockSymbol']}."
    )
    message.ack()


streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
logging.info(f"Listening to Pub Sub subscription: {subscription_path}...")


def streaming_pull_pub_sub_subscription():
    with subscriber:
        try:
            streaming_pull_future.result()
        except KeyboardInterrupt:
            streaming_pull_future.cancel()
        except TimeoutError:
            streaming_pull_future.cancel()
            streaming_pull_future.result()
