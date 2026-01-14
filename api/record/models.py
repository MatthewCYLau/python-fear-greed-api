from functools import wraps
import uuid
from bson import ObjectId
import pytz
import logging
from datetime import datetime, timezone, timedelta
from api.db.setup import db

GB = pytz.timezone("Europe/London")


def ensure_record_exists(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        record_id = args[0]
        record = db["records"].find_one({"_id": ObjectId(record_id)})

        if not record:
            raise ValueError(f"record {record_id} not found!")

        return f(record, *args, **kwargs)

    return decorator


class Record:
    def __init__(
        self, index, created=datetime.now(timezone.utc).astimezone(GB).isoformat()
    ):
        self.index = index
        self.created = created

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
                python_datetime = date.to_pydatetime()
                logging.info(f"Inserting record for {date} - {index_value}")
                logging.info(
                    f"Index of type {type(date)} to be converted to Python type {type(python_datetime)}"
                )
                # record = Record(
                #     str(index_value), created=python_datetime.astimezone(GB).isoformat()
                # )
                # record.save_to_database()
                inserted += 1
        return inserted

    @staticmethod
    @ensure_record_exists
    def update_record_created(
        record,
        record_id: uuid.UUID,
    ):
        update_record_operation = {
            "$set": {
                "created": datetime.fromisoformat(record["created"]),
            }
        }
        return db["records"].update_one(
            {"_id": ObjectId(record_id)}, update_record_operation, True
        )
