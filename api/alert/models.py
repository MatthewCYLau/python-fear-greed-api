import uuid
from datetime import datetime, timezone
from bson.objectid import ObjectId
from api.common.models import BaseModel
from api.db.setup import db
from api.auth.auth import auth_required


class Alert(BaseModel):
    def __init__(
        self, index, created, created_by, last_modified
    ):
        super().__init__(created, last_modified)
        self.index = index
        self.created_by = created_by

    @staticmethod
    def get_alerts(count: int = 0):
        alerts = list(db["alerts"].find({}).limit(count))
        for alert in alerts:
            if alert["created_by"]:
                alert["created_by"] = db["users"].find_one(
                    {"_id": ObjectId(alert["created_by"])}, {"password": False}
                )
        return alerts

    @staticmethod
    @auth_required
    def get_alert_by_id(_, alert_id: uuid.UUID):
        return db["alerts"].find_one({"_id": ObjectId(alert_id)})

    @staticmethod
    @auth_required
    def update_alert_by_id(_, alert_id: uuid.UUID, data: dict):
        updated_alert = {
            "$set": {
                "index": data["index"],
                "last_modified": datetime.now(timezone.utc),
            }
        }
        return db["alerts"].update_one(
            {"_id": ObjectId(alert_id)}, updated_alert, True
        )
