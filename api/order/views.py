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
