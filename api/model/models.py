from pydantic import BaseModel, ValidationInfo, field_validator

from api.util.util import check_asset_available


class ExportModelRequest(BaseModel):
    years: int
    stock: str

    @field_validator("years")
    @classmethod
    def check_years(cls, v: int, info: ValidationInfo) -> str:
        if v < 1 or v > 3:
            raise ValueError(f"{info.field_name} must be between 1 and 3 inclusive")
        return v

    @field_validator("stock")
    @classmethod
    def check_stock(cls, stock: str, info: ValidationInfo) -> str:
        if not check_asset_available(stock):
            raise ValueError(f"{info.field_name} is not a valid stock symbol")
        return stock
