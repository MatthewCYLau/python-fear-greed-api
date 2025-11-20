from enum import Enum
import logging

from pydantic import BaseModel, ValidationInfo, field_validator
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
                ]

                matching_buy_orders = list(
                    db["orders"].aggregate(matching_buy_orders_pipeline)
                )
                for j in matching_buy_orders:
                    logging.info(f"Buy order with ID {j['_id']} and price {j['price']}")
