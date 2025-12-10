import base64
from datetime import datetime
import json
import logging
from flask import Blueprint, jsonify, request
from google.cloud import pubsub_v1
import pandas as pd
from pydantic import ValidationError
from api.auth.auth import auth_required
from api.common.constants import DATETIME_FORMATE_CODE, ORDERS_TOPIC_NAME
from api.order.models import CreateOrderRequest, Order
from api.user.models import User
from api.util.util import generate_response, get_stock_price

bp = Blueprint("order", __name__)


@bp.route("/orders", methods=(["GET"]))
@auth_required
def get_orders(_):

    start_date = request.args.get("startDate")
    end_date = request.args.get("endDate")

    if start_date:
        start_date = datetime.strptime(start_date, DATETIME_FORMATE_CODE)

    if end_date:
        end_date = datetime.strptime(end_date, DATETIME_FORMATE_CODE)

    orders = Order.get_all(start_date, end_date)
    return generate_response(orders)


@bp.route("/orders", methods=(["POST"]))
@auth_required
def create_order(user):
    try:
        order_request = CreateOrderRequest.model_validate_json(request.data)
    except ValidationError as e:
        logging.error(e)
        return jsonify({"message": "Invalid payload"}), 400

    stock_symbol = order_request.stock_symbol
    order_type = order_request.order_type
    quantity = order_request.quantity
    price = order_request.price

    current_stock_price = round(get_stock_price(stock_symbol), 2)
    logging.info(f"{stock_symbol} current price: {current_stock_price}")

    order_price_total = price * quantity
    logging.info(f"Order price total: {order_price_total}")

    if order_type == "BUY" and user["balance"] < order_price_total:
        return (
            jsonify(
                {
                    "errors": [
                        {
                            "message": f"Insufficient fund! Balance of {user['balance']} is less than {order_price_total}"
                        }
                    ]
                }
            ),
            400,
        )

    if order_type == "SELL":
        matching_portfolio_stock = user.get("portfolio") and [
            i for i in user["portfolio"] if i["stock_symbol"] == stock_symbol
        ]
        if not matching_portfolio_stock:
            return (
                jsonify(
                    {
                        "errors": [
                            {
                                "message": f"Seller does not have {stock_symbol} in stock portfolio."
                            }
                        ]
                    }
                ),
                400,
            )
        portfolio_stock_quantity = matching_portfolio_stock[0]["quantity"]
        logging.info(f"{stock_symbol} portfolio quantity: {portfolio_stock_quantity}")
        if portfolio_stock_quantity < quantity:
            return (
                jsonify(
                    {
                        "errors": [
                            {
                                "message": f"Insufficient quantity! {stock_symbol} portfolio quantity {portfolio_stock_quantity} is less than sell order quantity {quantity}"
                            }
                        ]
                    }
                ),
                400,
            )

    try:
        publisher = pubsub_v1.PublisherClient()
        message_data_dict = {
            "user_id": str(user["_id"]),
            "stock_symbol": stock_symbol,
            "order_type": order_type,
            "quantity": quantity,
            "price": price,
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
        created_by = message_json["user_id"]
        stock_symbol = message_json["stock_symbol"]
        order_type = message_json["order_type"]
        quantity = message_json["quantity"]
        price = message_json["price"]
        logging.info(
            f"Received {order_type} for stock {stock_symbol}. Price {price} and quantity {quantity}"
        )

        new_order = Order(created_by, stock_symbol, order_type, quantity, price)

        new_order_id = new_order.save_to_db()
        logging.info(f"Created new order with id: {new_order_id}")

    return ("", 204)


@bp.route("/trades-subscription-push", methods=(["POST"]))
def handle_trades_subscription_push():
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
        sell_order_user_id = message_json["sell_order_user_id"]
        buy_order_user_id = message_json["buy_order_user_id"]
        stock_symbol = message_json["stock_symbol"]
        quantity = message_json["quantity"]
        price = message_json["price"]
        logging.info(
            f"Received trade request for stock {stock_symbol} from seller {sell_order_user_id} to buyer {buy_order_user_id}. Price {price} and quantity {quantity}"
        )

        try:
            res = User.increment_user_balance_by_id(
                user_id=sell_order_user_id,
                increment_amount=price * quantity,
            )
            if res.matched_count:
                logging.info("Seller balance updated")
        except Exception as e:
            logging.error(f"Failed to update seller balance - {e}")

        try:
            res = User.increment_user_balance_by_id(
                user_id=buy_order_user_id,
                increment_amount=-1 * price * quantity,
            )
            if res.matched_count:
                logging.info("Buyer balance updated")
        except Exception as e:
            logging.error(f"Failed to update buyer balance - {e}")

        try:
            res = User.increment_user_portfolio_quantity_by_id(
                user_id=sell_order_user_id,
                stock_symbol=stock_symbol,
                increment_amount=-1 * quantity,
            )
            if res.matched_count:
                logging.info("Seller portfolio updated")
        except Exception as e:
            logging.error(f"Failed to update seller portfolio - {e}")

        try:
            res = User.increment_user_portfolio_quantity_by_id(
                user_id=buy_order_user_id,
                stock_symbol=stock_symbol,
                increment_amount=quantity,
            )
            if res.matched_count:
                logging.info("Buyer portfolio updated")
        except Exception as e:
            logging.error(f"Failed to update buyer portfolio - {e}")

    return ("", 204)


@bp.route("/orders/match", methods=(["POST"]))
def match_orders():
    Order.match_orders()
    return ("", 204)


@bp.route("/orders/clean-up", methods=(["POST"]))
@auth_required
def delete_old_complete_orders(_):
    Order.delete_complete_orders_last_modified_days_ago()
    return ("", 204)


@bp.route("/orders/export-csv", methods=(["POST"]))
def export_orders_csv():
    orders = Order.get_all()
    df = pd.DataFrame(orders)

    # drop redundant columns
    df = df.drop(columns=["_id", "created_by", "last_modified"])

    # set created column as data frame index
    df["created"] = pd.to_datetime(df["created"], format="ISO8601", utc=True)
    df = df.set_index("created")

    df["created_date"] = df.index.date
    logging.info(df.tail())

    return ("", 204)
