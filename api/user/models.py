import uuid
from werkzeug.security import generate_password_hash
from bson.objectid import ObjectId
from api.common.models import BaseModel
from api.db.setup import db
from api.util.util import get_current_time_utc
from enum import Enum
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


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


class User(BaseModel):
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
    def increment_user_balance_by_id(user_id: uuid.UUID, increment_amount: float):
        try:
            Decimal(increment_amount)
        except InvalidOperation:
            raise TypeError("Balance amount must be a valid number.")
        except ValueError as e:
            raise e

        user = db["users"].find_one({"_id": ObjectId(user_id)})
        if user is not None:
            return db["users"].update_one(
                {"_id": user["_id"]},
                {"$inc": {"balance": round(increment_amount, 2)}},
                True,
            )

    @staticmethod
    def update_user_portfolio_by_id(user_id: uuid.UUID, portfolio_data: dict = {}):
        user = db["users"].find_one({"_id": ObjectId(user_id)})

        if not user:
            pass

        if not user.get("portfolio"):
            updated_user = {
                "$set": {
                    "portfolio": [
                        {"stock_symbol": "AAPL", "quantity": 10},
                        {"stock_symbol": "TSLA", "quantity": 10},
                        {"stock_symbol": "META", "quantity": 10},
                    ]
                }
            }
            return db["users"].update_one({"_id": user["_id"]}, updated_user, True)

        else:
            matching_portfolio_stock = list(
                filter(
                    lambda n: n["stock_symbol"] == portfolio_data["stock_symbol"],
                    user["portfolio"],
                )
            )
            if not matching_portfolio_stock:
                update_operation = {"$push": {"portfolio": portfolio_data}}
                return db["users"].update_one(
                    {
                        "_id": user["_id"],
                    },
                    update_operation,
                )
            else:
                updated_user = {
                    "$set": {"portfolio.$.quantity": portfolio_data["quantity"]}
                }
                return db["users"].update_one(
                    {
                        "_id": user["_id"],
                        "portfolio.stock_symbol": portfolio_data["stock_symbol"],
                    },
                    updated_user,
                    True,
                )

    @staticmethod
    def increment_user_portfolio_quantity_by_id(
        user_id: uuid.UUID, stock_symbol: str, increment_amount: int
    ):
        user = db["users"].find_one({"_id": ObjectId(user_id)})
        if user and user.get("portfolio"):
            updated_user = {"$inc": {"portfolio.$.quantity": increment_amount}}
            return db["users"].update_one(
                {
                    "_id": user["_id"],
                    "portfolio.stock_symbol": stock_symbol,
                },
                updated_user,
                True,
            )
