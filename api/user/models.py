import uuid
from pydantic import BaseModel, ValidationInfo, field_validator
from werkzeug.security import generate_password_hash
from bson.objectid import ObjectId
from api.common.constants import DJI_TICKER, NASDAQ_TICKER, SNP_TICKER
from api.common.models import BaseModel as CommonBaseModel
from api.db.setup import db
from api.util.util import (
    calculate_new_stock_cost_basis,
    check_asset_available,
    get_current_time_utc,
    get_portfolio_alpha,
    get_stock_current_price,
    get_user_portfolio_analysis_df,
    get_user_portfolio_roi_series,
)
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from functools import wraps


class UserType(str, Enum):
    INDIVIDUAL_INVESTOR = "INDIVIDUAL_INVESTOR"
    INSTITUTIONAL_INVESTOR = "INSTITUTIONAL_INVESTOR"


class Currency(Enum):
    GBP = 1
    USD = 2
    EUR = 3


@dataclass
class TestUserType:
    userType: UserType


def ensure_user_exists(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        user_id = kwargs["user_id"]
        user = db["users"].find_one({"_id": ObjectId(user_id)})

        if not user:
            raise ValueError(f"User {user_id} not found!")

        return f(user, *args, **kwargs)

    return decorator


class UpdateUserPortfolioRequest(BaseModel):

    stock_symbol: str
    quantity: int

    @field_validator("stock_symbol")
    @classmethod
    def check_stock(cls, stock_symbol: str, info: ValidationInfo) -> str:
        if not check_asset_available(stock_symbol):
            raise ValueError(f"{info.field_name} is not a valid stock symbol")
        return stock_symbol


class PlotPortfolioRoiRequest(BaseModel):

    benchmark_stock_symbol: str

    @field_validator("benchmark_stock_symbol")
    @classmethod
    def check_stock(cls, benchmark_stock_symbol: str, info: ValidationInfo) -> str:
        if not check_asset_available(
            benchmark_stock_symbol
        ) or benchmark_stock_symbol not in [SNP_TICKER, DJI_TICKER, NASDAQ_TICKER]:
            raise ValueError(
                f"{info.field_name} is not a valid stock symbol, or not a supported benchmark."
            )
        return benchmark_stock_symbol


class User(CommonBaseModel):
    def __init__(
        self,
        email,
        password,
        name,
        isEmailVerified,
        avatarImageUrl="",
        regularContributionAmount=0,
        currency=Currency.GBP,
        userType=UserType.INDIVIDUAL_INVESTOR,
        balance=1_000_000,
        portfolio=[],
    ):
        super().__init__()
        self.email = email
        self.password = password
        self.name = name
        self.isEmailVerified = isEmailVerified
        self.avatarImageUrl = avatarImageUrl
        self.userType = userType
        self.balance = balance
        self.portfolio = portfolio
        try:
            Decimal(regularContributionAmount)
            self.regularContributionAmount = regularContributionAmount
        except InvalidOperation:
            raise TypeError("Regular contribution amount must be a valid number.")
        except ValueError as e:
            raise e
        if not isinstance(currency, Currency):
            raise TypeError("Invalid currency.")
        self.currency = currency.name

    def save_user_to_db(self):
        self.password = generate_password_hash(self.password, method="sha256")
        res = db.users.insert_one(vars(self))
        return res.inserted_id

    @staticmethod
    def get_user_by_email(email):
        return db["users"].find_one({"email": email})

    @staticmethod
    def update_user_by_id(user_id: uuid.UUID, data: dict):

        if data.get("balance"):
            balance = data["balance"]
            try:
                Decimal(balance)
            except InvalidOperation:
                raise TypeError("Balance amount must be a valid number.")
            except ValueError as e:
                raise e

            user = db["users"].find_one({"_id": ObjectId(user_id)})
            if user is not None:
                updated_user = {
                    "$set": {
                        "balance": data["balance"],
                    }
                }
                return db["users"].update_one({"_id": user["_id"]}, updated_user, True)

        regular_contribution_amount = data.get("regularContributionAmount", 0)
        try:
            Decimal(regular_contribution_amount)
        except InvalidOperation:
            raise TypeError("Regular contribution amount must be a valid number.")
        except ValueError as e:
            raise e
        updated_user = {
            "$set": {
                "email": data["email"],
                "name": data["name"],
                "last_modified": get_current_time_utc(),
                "avatarImageUrl": data["avatarImageUrl"],
                "regularContributionAmount": regular_contribution_amount,
                "currency": data.get("currency", Currency["GBP"].name),
            }
        }
        if "password" in data:
            updated_user["$set"]["password"] = generate_password_hash(
                data["password"], method="sha256"
            )
        return db["users"].update_one({"_id": ObjectId(user_id)}, updated_user, True)

    def update_user_as_email_verified(email):
        user = User.get_user_by_email(email)
        if user is not None:
            updated_user = {
                **user,
                "isEmailVerified": True,
                "last_modified": get_current_time_utc(),
            }
            return db["users"].update_one({"_id": user["_id"]}, updated_user, True)

    @staticmethod
    @ensure_user_exists
    def increment_user_balance_by_id(_, user_id: uuid.UUID, increment_amount: float):
        try:
            Decimal(increment_amount)
        except InvalidOperation:
            raise TypeError("Balance amount must be a valid number.")
        except ValueError as e:
            raise e

        return db["users"].update_one(
            {"_id": ObjectId(user_id)},
            {"$inc": {"balance": round(increment_amount, 2)}},
            True,
        )

    @staticmethod
    @ensure_user_exists
    def update_user_portfolio_by_id(
        user, user_id: uuid.UUID, portfolio_data: dict = {}
    ):
        if "portfolio" not in user:
            updated_user = {
                "$set": {
                    "portfolio": [
                        {
                            "stock_symbol": "AAPL",
                            "quantity": 10,
                            "cost_basis": get_stock_current_price("AAPL"),
                        },
                        {
                            "stock_symbol": "TSLA",
                            "quantity": 10,
                            "cost_basis": get_stock_current_price("TSLA"),
                        },
                        {
                            "stock_symbol": "META",
                            "quantity": 10,
                            "cost_basis": get_stock_current_price("META"),
                        },
                    ],
                    "last_modified": get_current_time_utc(),
                }
            }
            return db["users"].update_one(
                {"_id": ObjectId(user_id)}, updated_user, True
            )

        else:
            matching_portfolio_stock = list(
                filter(
                    lambda n: n["stock_symbol"] == portfolio_data["stock_symbol"],
                    user["portfolio"],
                )
            )
            if not matching_portfolio_stock:
                update_operation = {
                    "$push": {
                        "portfolio": portfolio_data
                        | {
                            "cost_basis": get_stock_current_price(
                                portfolio_data["stock_symbol"]
                            )
                        }
                    },
                    "$set": {
                        "last_modified": get_current_time_utc(),
                    },
                }
                return db["users"].update_one(
                    {
                        "_id": ObjectId(user_id),
                    },
                    update_operation,
                )
            else:
                updated_user = {
                    "$set": {
                        "portfolio.$.quantity": portfolio_data["quantity"],
                        "portfolio.$.cost_basis": calculate_new_stock_cost_basis(
                            old_total_cost=matching_portfolio_stock[0]["quantity"]
                            * matching_portfolio_stock[0].get("cost_basis", 0),
                            new_purchase_cost=portfolio_data["quantity"]
                            * get_stock_current_price(portfolio_data["stock_symbol"]),
                            old_total_shares=matching_portfolio_stock[0]["quantity"],
                            new_shares_bought=portfolio_data["quantity"],
                        ),
                        "last_modified": get_current_time_utc(),
                    }
                }
                return db["users"].update_one(
                    {
                        "_id": ObjectId(user_id),
                        "portfolio.stock_symbol": portfolio_data["stock_symbol"],
                    },
                    updated_user,
                    True,
                )

    @staticmethod
    @ensure_user_exists
    def increment_user_portfolio_quantity_by_id(
        user, user_id: uuid.UUID, stock_symbol: str, increment_amount: int
    ):
        if user.get("portfolio"):
            updated_user = {
                "$inc": {"portfolio.$.quantity": increment_amount},
                "$set": {
                    "last_modified": get_current_time_utc(),
                },
            }
            return db["users"].update_one(
                {
                    "_id": ObjectId(user_id),
                    "portfolio.stock_symbol": stock_symbol,
                },
                updated_user,
                True,
            )

    @staticmethod
    @ensure_user_exists
    def remove_user_portfolio_stock_by_id(user, user_id: uuid.UUID, stock_symbol: str):
        if user.get("portfolio"):
            updated_operation = {
                "$pull": {"portfolio": {"stock_symbol": stock_symbol}},
                "$set": {
                    "last_modified": get_current_time_utc(),
                },
            }
            return db["users"].update_one(
                {
                    "_id": ObjectId(user_id),
                },
                updated_operation,
                True,
            )

    @staticmethod
    @ensure_user_exists
    def get_user_portfolio_analysis(
        user,
        user_id: uuid.UUID,
    ):
        if user.get("portfolio"):
            portfolio_data = user.get("portfolio")
            portfolio_df = get_user_portfolio_analysis_df(portfolio_data)

            total_value = portfolio_df["market_value"].sum()
            total_invested = (
                portfolio_df["quantity"] * portfolio_df["buy_price"]
            ).sum()
            portfolio_roi = ((total_value - total_invested) / total_invested) * 100
            portfolio_alpha = get_portfolio_alpha(portfolio_roi)

            for i in portfolio_data:
                i["weight"] = round(
                    portfolio_df[
                        portfolio_df["stock_symbol"] == i["stock_symbol"]
                    ].iloc[-1]["weight"],
                    2,
                )
                i["market_value"] = round(
                    portfolio_df[
                        portfolio_df["stock_symbol"] == i["stock_symbol"]
                    ].iloc[-1]["market_value"],
                    2,
                )
                i["return"] = portfolio_df[
                    portfolio_df["stock_symbol"] == i["stock_symbol"]
                ].iloc[-1]["return"]
                i["sector"] = portfolio_df[
                    portfolio_df["stock_symbol"] == i["stock_symbol"]
                ].iloc[-1]["sector"]
            return {
                "total_value": round(total_value, 2),
                "portfolio_data": portfolio_data,
                "portfolio_roi": round(portfolio_roi, 2),
                "portfolio_alpha": round(portfolio_alpha, 2),
            }
        return {}

    @staticmethod
    @ensure_user_exists
    def get_user_portfolio_roi_series(
        user, user_id: uuid.UUID, benchmark: str = "^GSPC"
    ):
        if user.get("portfolio"):
            portfolio_data = user.get("portfolio")
            portfolio_roi, benchmark_roi = get_user_portfolio_roi_series(
                portfolio_data, benchmark
            )
            return portfolio_roi, benchmark_roi
