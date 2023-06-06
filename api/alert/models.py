import uuid
from bson.objectid import ObjectId
from api.common.models import BaseModel
from api.db.setup import db
from api.auth.auth import auth_required
from api.util.util import get_current_time_gb


class Alert(BaseModel):
    def __init__(
        self,
        index,
        created_by,
    ):
        super().__init__()
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
            "$set": {"index": data["index"], "last_modified": get_current_time_gb()}
        }
        return db["alerts"].update_one({"_id": ObjectId(alert_id)}, updated_alert, True)