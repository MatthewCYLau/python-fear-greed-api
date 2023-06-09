import uuid
from bson.objectid import ObjectId
from api.db.setup import db


class Event:
    @staticmethod
    def get_events_by_created_by(created_by: uuid.UUID):
        alerts = list(
            db["alerts"].find({"created_by": ObjectId(created_by)}).sort("_id", -1)
        )

        alert_ids = [i["_id"] for i in alerts]

        events = list(
            db["events"]
            .find({"alert_id": {"$in": [ObjectId(i) for i in alert_ids]}})
            .sort("_id", -1)
        )
        return events
