import pytz
from datetime import datetime, timezone

GB = pytz.timezone("Europe/London")


class Record:
    def __init__(self, index):
        self.index = index
        self.creatd = datetime.now(timezone.utc).astimezone(GB).isoformat()
