from datetime import datetime
from pydantic import BaseModel, ValidationInfo, field_validator

from api.common.constants import PANDAS_DF_DATE_FORMATE_CODE
from api.util.util import (
    check_asset_available,
    validate_date_string_for_pandas_df,
)


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


class PredictStockFromModelRequest(BaseModel):
    future_date: str
    stock: str
    pkl_model_id: str

    @field_validator("future_date")
    @classmethod
    def check_years(cls, v: str) -> str:
        if not (validate_date_string_for_pandas_df(v)):
            raise ValueError("Invalid date input. Must be in format DD-MM-YYYY")

        now = datetime.now()
        future_days = (datetime.strptime(v, PANDAS_DF_DATE_FORMATE_CODE) - now).days

        if future_days < 1:
            raise ValueError("Futre date must be at least one full day in future!")

        return v

    @field_validator("stock")
    @classmethod
    def check_stock(cls, stock: str, info: ValidationInfo) -> str:
        if not check_asset_available(stock):
            raise ValueError(f"{info.field_name} is not a valid stock symbol")
        return stock
