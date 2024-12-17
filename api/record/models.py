import pytz
import logging
from datetime import datetime, timezone, timedelta
from api.db.setup import db

GB = pytz.timezone("Europe/London")


class Record:
    def __init__(self, index):
        self.index = index
        self.creatd = datetime.now(timezone.utc).astimezone(GB).isoformat()

    def save_to_database(self):
        db["records"].insert_one(vars(self))
        logging.info(f"Saved record to database - {self.index}")

    @staticmethod
    def get_most_recent_record():
        return list(db["records"].find().sort("created", -1).limit(0))[0]

    @staticmethod
    def _get_records_created_within_next_days(start_date: datetime, next_days: int = 1):
        return list(
            db["records"].find(
                {
                    "created": {
                        "$gte": start_date.isoformat(),
                        "$lte": (start_date + timedelta(days=next_days)).isoformat(),
                    }
                }
            )
        )

    @staticmethod
    def import_from_dataframe(df) -> int:
        inserted = 0
        for index, row in df.iterrows():
            date = index
            index_value = row["Index"]
            count = len(Record._get_records_created_within_next_days(date))
            if count:
                logging.info(
                    f"Skipping inserting record for {date} - {index_value} - count of records next day: {count}"
                )
            else:
                logging.info(f"Inserting record for {date} - {index_value}")
                inserted += 1
        return inserted
