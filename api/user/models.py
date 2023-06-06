import uuid
from werkzeug.security import generate_password_hash
from bson.objectid import ObjectId
from api.common.models import BaseModel
from api.db.setup import db
from api.auth.auth import auth_required
from api.util.util import get_current_time_gb


class User(BaseModel):
    def __init__(
        self,
        email,
        password,
        name,
        isEmailVerified,
    ):
        super().__init__()
        self.email = email
        self.password = password
        self.name = name
        self.isEmailVerified = isEmailVerified

    def save_user_to_db(self):
        self.password = generate_password_hash(self.password, method="sha256")
        res = db.users.insert_one(vars(self))
        return res.inserted_id

    @staticmethod
    def get_user_by_email(email):
        return db["users"].find_one({"email": email})

    @staticmethod
    @auth_required
    def update_user_by_id(_, user_id: uuid.UUID, data: dict):
        updated_user = {
            "$set": {
                "email": data["email"],
                "password": generate_password_hash(data["password"], method="sha256"),
                "name": data["name"],
                "last_modified": get_current_time_gb(),
            }
        }
        return db["users"].update_one({"_id": ObjectId(user_id)}, updated_user, True)

    def update_user_as_email_verified(email):
        user = User.get_user_by_email(email)
        if user is not None:
            updated_user = {
                **user,
                "isEmailVerified": True,
                "last_modified": get_current_time_gb(),
            }
            return db["users"].update_one({"_id": user["_id"]}, updated_user, True)
