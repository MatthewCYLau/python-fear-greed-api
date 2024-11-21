import pytz
import uuid
from bson.objectid import ObjectId
from api.common.models import BaseModel
from api.util.util import get_current_time_utc
from api.db.setup import db
from datetime import datetime, timedelta

GB = pytz.timezone("Europe/London")


class AnalysisJob(BaseModel):
    def __init__(
        self,
        stock_symbol,
        created_by,
        most_recent_fear_greed_index=0,
        current_pe_ratio=0,
        target_fear_greed_index=0,
        target_pe_ratio=0,
        fair_value=0,
        delta=0,
    ):
        super().__init__()
        self.stock_symbol = stock_symbol
        self.created_by = created_by
        self.most_recent_fear_greed_index = most_recent_fear_greed_index
        self.current_pe_ratio = current_pe_ratio
        self.target_fear_greed_index = target_fear_greed_index
        self.target_pe_ratio = target_pe_ratio
        self.fair_value = fair_value
        self.delta = delta
        self.complete = False

    def save_analysis_job_to_db(self):
        res = db.analysis_jobs.insert_one(vars(self))
        return res.inserted_id

    @staticmethod
    def update_analysis_job_by_id(analysis_job_id: uuid.UUID, data: dict = {}):
        updated_analysis_job = {
            "$set": {
                "most_recent_fear_greed_index": data["most_recent_fear_greed_index"],
                "current_pe_ratio": data["current_pe_ratio"],
                "target_fear_greed_index": data["target_fear_greed_index"],
                "target_pe_ratio": data["target_pe_ratio"],
                "fair_value": data["fair_value"],
                "delta": data["delta"],
                "complete": data["complete"],
                "last_modified": get_current_time_utc(),
            }
        }
        return db["analysis_jobs"].update_one(
            {"_id": ObjectId(analysis_job_id)}, updated_analysis_job, True
        )

    @staticmethod
    def get_analysis_jobs_by_created_by_within_hours(
        created_by: uuid.UUID, hours: int = 24
    ):
        alerts = list(
            db["analysis_jobs"].find(
                {
                    "$and": [
                        {"created_by": ObjectId(created_by)},
                        {
                            "created": {
                                "$lt": datetime.now(),
                                "$gt": datetime.now() - timedelta(hours=hours),
                            }
                        },
                    ]
                }
            )
        )
        return alerts
