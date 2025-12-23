from datetime import datetime, timedelta
from enum import Enum
from functools import wraps
import json
import logging
import uuid
from google.cloud import pubsub_v1
from bson import ObjectId
from pydantic import BaseModel, ValidationInfo, field_validator
from api.common.constants import TRADES_TOPIC_NAME
from api.common.models import BaseModel as CommonBaseModel
from api.db.setup import db
from api.util.util import check_asset_available, get_current_time_utc


class OrderType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


def ensure_order_exists(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        order_id = args[0]
        order = db["orders"].find_one({"_id": ObjectId(order_id)})

        if not order:
            raise ValueError(f"Order {order_id} not found!")

        return f(order, *args, **kwargs)

    return decorator


class CreateOrderRequest(BaseModel):

    stock_symbol: str
    order_type: str
    quantity: int
    price: float

    @field_validator("order_type")
    @classmethod
    def check_order_type(cls, order_type: str, info: ValidationInfo) -> str:
        if order_type not in [OrderType.BUY, OrderType.SELL]:
            raise ValueError(
                f"{info.field_name} must be one {[OrderType.BUY, OrderType.SELL]}"
            )
        return order_type

    @field_validator("stock_symbol")
    @classmethod
    def check_stock(cls, stock_symbol: str, info: ValidationInfo) -> str:
        if not check_asset_available(stock_symbol):
            raise ValueError(f"{info.field_name} is not a valid stock symbol")
        return stock_symbol


class UpdateOrderRequest(BaseModel):
    quantity: int
    price: float


class Order(CommonBaseModel):
    def __init__(
        self, created_by, stock_symbol, order_type, quantity, price, status="open"
    ):
        super().__init__()
        self.created_by = created_by
        self.stock_symbol = stock_symbol
        self.order_type = order_type
        self.quantity = quantity
        self.price = price
        self.status = status

    def save_to_db(self):
        res = db.orders.insert_one(vars(self))
        return res.inserted_id

    @staticmethod
    def get_all(
        start_date: datetime = None,
        end_date: datetime = None,
        page_size: int = 5,
        current_page: int = 1,
    ):

        if start_date and end_date:
            query = {
                "created": {"$gte": start_date, "$lt": end_date + timedelta(days=1)}
            }
        else:
            query = {}
        orders = list(
            db["orders"]
            .find(query)
            .sort("created", -1)
            .skip((current_page - 1) * page_size)
            .limit(page_size)
        )
        return orders

    @staticmethod
    def get_order_by_id(order_id: uuid.UUID):
        return db["orders"].find_one({"_id": ObjectId(order_id)})

    @staticmethod
    @ensure_order_exists
    def update_order_status(_, order_id: uuid.UUID, new_status: str = "complete"):
        update_order_operation = {
            "$set": {
                "status": new_status,
                "last_modified": get_current_time_utc(),
            }
        }
        return db["orders"].update_one(
            {"_id": ObjectId(order_id)}, update_order_operation, True
        )

    @staticmethod
    @ensure_order_exists
    def increment_order_quantity(_, order_id: uuid.UUID, increment_amount: int):
        return db["orders"].update_one(
            {"_id": ObjectId(order_id)},
            {
                "$inc": {"quantity": increment_amount},
                "$set": {
                    "last_modified": get_current_time_utc(),
                },
            },
            True,
        )

    @staticmethod
    def process_sell_and_buy_orders(sell_order_id: uuid.UUID, buy_order_id: uuid.UUID):

        sell_order = Order.get_order_by_id(sell_order_id)
        logging.info(
            f"Sell order for stock {sell_order['stock_symbol']} at price {sell_order['price']} for quantity {sell_order['quantity']}"
        )
        buy_order = Order.get_order_by_id(buy_order_id)
        logging.info(
            f"Buy order for stock {buy_order['stock_symbol']} at price {buy_order['price']} for quantity {buy_order['quantity']}"
        )

        trade_quantity = min(sell_order["quantity"], buy_order["quantity"])
        trade_details = {
            "stock_symbol": sell_order["stock_symbol"],
            "price": min(sell_order["price"], buy_order["price"]),
            "quantity": trade_quantity,
            "sell_order_user_id": str(sell_order["created_by"]),
            "buy_order_user_id": str(buy_order["created_by"]),
        }
        logging.info(trade_details)

        Order.increment_order_quantity(sell_order_id, trade_quantity * -1)
        Order.increment_order_quantity(buy_order_id, trade_quantity * -1)

        if sell_order["quantity"] == trade_quantity:
            Order.update_order_status(sell_order_id, "complete")
        if buy_order["quantity"] == trade_quantity:
            Order.update_order_status(buy_order_id, "complete")

        try:
            publisher = pubsub_v1.PublisherClient()
            message_data_encode = json.dumps(trade_details, indent=2).encode("utf-8")
            future = publisher.publish(TRADES_TOPIC_NAME, message_data_encode)
            message_id = future.result()
            return message_id
        except Exception as e:
            logging.error(e)

    @staticmethod
    def match_orders():
        open_orders_distinct_stock_symbols = (
            db["orders"].find({"status": "open"}).distinct("stock_symbol")
        )
        logging.info(f"Open orders stock symbol: {open_orders_distinct_stock_symbols}")

        for i in open_orders_distinct_stock_symbols:
            stock_sell_orders_query = {"stock_symbol": i, "order_type": "SELL"}
            stock_buy_orders_query = {"stock_symbol": i, "order_type": "BUY"}

            stock_sell_orders = list(db["orders"].find(stock_sell_orders_query))
            stock_buy_orders = list(db["orders"].find(stock_buy_orders_query))

            if not stock_sell_orders or not stock_buy_orders:
                logging.info(f"No matching orders for stock symbol: {i}")
            else:
                logging.info(f"Process matching orders for stock symbol: {i}...")
                min_sell_price_pipeline = [
                    {"$match": {"stock_symbol": i}},
                    {"$match": {"status": "open"}},
                    {"$match": {"order_type": "SELL"}},
                    {
                        "$group": {
                            "_id": "$stock_symbol",
                            "minPrice": {"$min": "$price"},
                        }
                    },
                ]
                min_sell_price = list(db["orders"].aggregate(min_sell_price_pipeline))[
                    0
                ]["minPrice"]
                logging.info(f"{i} minimum sell price is {min_sell_price}")

                matching_buy_orders_pipeline = [
                    {"$match": {"stock_symbol": i}},
                    {"$match": {"status": "open"}},
                    {"$match": {"order_type": "BUY"}},
                    {"$match": {"price": {"$gt": min_sell_price}}},
                    {"$sort": {"_id": 1}},
                ]

                matching_buy_orders = list(
                    db["orders"].aggregate(matching_buy_orders_pipeline)
                )
                for j in matching_buy_orders:
                    logging.info(
                        f"Buy order with ID {j['_id']} at price {j['price']} is above minimum sell price"
                    )

                if matching_buy_orders:
                    sell_order_at_min_price_pipeline = [
                        {"$match": {"stock_symbol": i}},
                        {"$match": {"status": "open"}},
                        {
                            "$match": {
                                "created_by": {
                                    "$ne": matching_buy_orders[0]["created_by"]
                                }
                            }
                        },
                        {"$sort": {"price": 1}},
                        {
                            "$group": {
                                "_id": "$stock_symbol",
                                "order_id": {"$first": "$_id"},
                                "price": {"$first": "$price"},
                            }
                        },
                    ]
                    sell_order_at_min_price = list(
                        db["orders"].aggregate(sell_order_at_min_price_pipeline)
                    )[0]
                    logging.info(
                        f"Sell order with ID {sell_order_at_min_price['order_id']} at price {sell_order_at_min_price['price']} to be matched with first buy order."
                    )

                    Order.process_sell_and_buy_orders(
                        sell_order_at_min_price["order_id"],
                        matching_buy_orders[0]["_id"],
                    )

    @staticmethod
    def delete_complete_orders_last_modified_days_ago(days_ago: int = 5):
        return db["orders"].delete_many(
            {
                "status": "complete",
                "last_modified": {
                    "$lte": get_current_time_utc() - timedelta(days=days_ago)
                },
            }
        )

    @staticmethod
    def update_order_by_id(order_id: uuid.UUID, quantity: int, price: float):
        update_operation = {"$set": {"quantity": quantity, "price": price}}
        return db["orders"].update_one(
            {"_id": ObjectId(order_id)}, update_operation, True
        )
