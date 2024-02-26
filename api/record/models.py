import pytz
from datetime import datetime, timezone
from api.db.setup import db

GB = pytz.timezone("Europe/London")


class Record:
    def __init__(self, index):
        self.index = index
        self.creatd = datetime.now(timezone.utc).astimezone(GB).isoformat()

    @staticmethod
    def get_most_recent_record():
        return list(db["records"].find().sort("created", -1).limit(0))[0]
