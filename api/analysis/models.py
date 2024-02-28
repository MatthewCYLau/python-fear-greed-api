import pytz
import uuid
import random
from bson.objectid import ObjectId
from api.common.models import BaseModel
from api.util.util import get_current_time_gb
from api.db.setup import db

GB = pytz.timezone("Europe/London")


class AnalysisJob(BaseModel):
    def __init__(self, stock_symbol, fair_value=0):
        super().__init__()
        self.stock_symbol = stock_symbol
        self.fair_value = fair_value
        self.complete = False

    def save_analysis_job_to_db(self):
        res = db.analysis_jobs.insert_one(vars(self))
        return res.inserted_id

    @staticmethod
    def update_analysis_job_by_id(analysis_job_id: uuid.UUID, data: dict = {}):
        updated_analysis_job = {
            "$set": {
                "fair_value": data["fair_value"],
                "complete": data["complete"],
                "last_modified": get_current_time_gb(),
            }
        }
        return db["analysis_jobs"].update_one(
            {"_id": ObjectId(analysis_job_id)}, updated_analysis_job, True
        )
