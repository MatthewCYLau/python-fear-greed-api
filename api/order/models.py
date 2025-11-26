from enum import Enum
import json
import logging
import uuid
from google.cloud import pubsub_v1
from bson import ObjectId
from pydantic import BaseModel, ValidationInfo, field_validator
from api.common.constants import TRADES_TOPIC_NAME
from api.common.models import BaseModel as CommonBaseModel
from api.db.setup import db
from api.util.util import check_asset_available


class OrderType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


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
    def get_all():
        orders = list(db["orders"].find({}))
        return orders

    @staticmethod
    def get_order_by_id(order_id: uuid.UUID):
        return db["orders"].find_one({"_id": ObjectId(order_id)})

    @staticmethod
    def update_order_status(order_id: uuid.UUID, new_status: str = "complete"):
        order = Order.get_order_by_id(order_id)
        if order:
            updated_order = {
                "$set": {
                    "status": new_status,
                }
            }
            return db["users"].update_one(
                {"_id": ObjectId(order_id)}, updated_order, True
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

        try:
            publisher = pubsub_v1.PublisherClient()
            message_data_encode = json.dumps(trade_details, indent=2).encode("utf-8")
            future = publisher.publish(TRADES_TOPIC_NAME, message_data_encode)
            message_id = future.result()
            return message_id
        except Exception as e:
            logging.error(e)

        if sell_order["quantity"] == trade_quantity:
            Order.update_order_status(sell_order_id, "complete")
        if buy_order["quantity"] == trade_quantity:
            Order.update_order_status(buy_order_id, "complete")

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
