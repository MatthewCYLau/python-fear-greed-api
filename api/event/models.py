import uuid
from bson.objectid import ObjectId
from api.util.util import value_is_true
from api.db.setup import db


class Event:
    @staticmethod
    def get_events_by_alert_created_by(
        created_by: uuid.UUID, acknowledged: bool = False
    ):
        alerts = list(
            db["alerts"].find({"created_by": ObjectId(created_by)}).sort("_id", -1)
        )

        alert_ids = [i["_id"] for i in alerts]

        events = list(
            db["events"]
            .find(
                {
                    "$and": [
                        {"alert_id": {"$in": [ObjectId(i) for i in alert_ids]}},
                        {"acknowledged": acknowledged},
                    ]
                }
            )
            .sort("_id", -1)
        )
        return events

    @staticmethod
    def update_event_by_id(event_id: uuid.UUID, data: dict = {}):
        updated_event = {
            "$set": {
                "acknowledged": value_is_true(data["acknowledged"]),
            }
        }
        return db["events"].update_one({"_id": ObjectId(event_id)}, updated_event, True)
