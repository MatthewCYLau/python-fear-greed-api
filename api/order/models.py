from api.common.models import BaseModel


class Order(BaseModel):
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
