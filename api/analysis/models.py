import pytz
from api.common.models import BaseModel
from api.db.setup import db

GB = pytz.timezone("Europe/London")


class AnalysisJob(BaseModel):
    def __init__(self, stock_symbol, fair_value=0):
        super().__init__()
        self.stock_symbol = stock_symbol
        self.fair_value = fair_value

    def save_analysis_job_to_db(self):
        res = db.analysis_jobs.insert_one(vars(self))
        return res.inserted_id
