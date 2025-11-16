import base64
import json
import logging
from flask import Blueprint, jsonify, request
from google.cloud import pubsub_v1
from api.auth.auth import auth_required
from api.common.constants import ORDERS_TOPIC_NAME

bp = Blueprint("order", __name__)


@bp.route("/orders", methods=(["POST"]))
@auth_required
def create_order(user):
    data = request.get_json()
    try:
        publisher = pubsub_v1.PublisherClient()
        message_data_dict = {
            "user_id": str(user["_id"]),
            "stock_symbol": data.get("stock_symbol"),
            "order_type": data.get("order_type"),
            "quantity": data.get("quantity"),
            "price": data.get("price"),
        }
        message_data_encode = json.dumps(message_data_dict, indent=2).encode("utf-8")
        future = publisher.publish(ORDERS_TOPIC_NAME, message_data_encode)
        message_id = future.result()
        return (
            jsonify({"message_id": message_id}),
            200,
        )
    except Exception as e:
        logging.error(e)
        return jsonify({"message": "Create order failed"}), 500


@bp.route("/orders-subscription-push", methods=(["POST"]))
def handle_orders_subscription_push():
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
        stock_symbol = message_json["stock_symbol"]
        order_type = message_json["order_type"]
        quantity = message_json["quantity"]
        price = message_json["price"]
        logging.info(
            f"Received {order_type} for stock {stock_symbol}. Price {price} and quantity {quantity}"
        )

    return ("", 204)
