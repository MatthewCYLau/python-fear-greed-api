import uuid
from bson.objectid import ObjectId
from api.common.models import BaseModel
from api.db.setup import db
from api.util.util import get_current_time_utc


class Alert(BaseModel):
    def __init__(
        self,
        index,
        note,
        created_by,
        view_count=0,
        have_actioned=False,
    ):
        super().__init__()
        self.index = index
        self.note = note
        self.created_by = created_by
        self.view_count = view_count
        self.have_actioned = have_actioned

    @staticmethod
    def get_alerts(count: int = 0, max_index: int = 100):
        alerts = list(
            db["alerts"]
            .find({"index": {"$lt": max_index + 1}})
            .sort("_id", -1)
            .limit(count)
        )
        for alert in alerts:
            if alert["created_by"]:
                alert["created_by"] = db["users"].find_one(
                    {"_id": ObjectId(alert["created_by"])}, {"password": False}
                )
        return alerts

    @staticmethod
    def get_alert_by_id(alert_id: uuid.UUID):
        return db["alerts"].find_one({"_id": ObjectId(alert_id)})

    @staticmethod
    def get_alerts_by_created_by(created_by: uuid.UUID):
        alerts = list(
            db["alerts"].find({"created_by": ObjectId(created_by)}).sort("_id", -1)
        )
        for alert in alerts:
            if alert["created_by"]:
                alert["created_by"] = db["users"].find_one(
                    {"_id": ObjectId(alert["created_by"])}, {"password": False}
                )
        return alerts

    @staticmethod
    def update_alert_by_id(alert_id: uuid.UUID, data: dict):
        updated_alert = {
            "$set": {
                "index": data["index"],
                "note": data["note"],
                "have_actioned": data["have_actioned"],
                "last_modified": get_current_time_utc(),
            }
        }
        return db["alerts"].update_one({"_id": ObjectId(alert_id)}, updated_alert, True)

    @staticmethod
    def increment_alert_view_count_by_id(alert_id: uuid.UUID):
        return db["alerts"].find_one_and_update(
            {"_id": ObjectId(alert_id)}, {"$inc": {"view_count": 1}}
        )
