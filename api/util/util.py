from functools import cache
from flask import jsonify
from datetime import datetime, timezone
from api.common.constants import DATETIME_FORMATE_CODE
import json


def generate_response(input):
    """Returns a reponse which over-writes Mongo ObjectID"""
    return jsonify(json.loads(json.dumps(input, default=lambda o: str(o))))


def transform_to_formatted_string(input):
    """Returns a formatted string which over-writes Mongo ObjectID"""
    return json.dumps(input, default=lambda o: str(o))


def generate_response_from_redis(input):
    """Returns a response from redis value"""
    return jsonify(json.loads(input))


def return_dupliucated_items_in_list(input_list):
    return set([x for x in input_list if input_list.count(x) > 1])


def is_valid_sector(sector):
    return sector in ["Financial Services", "Public Sector", "Private Sector"]


def get_current_time_utc():
    return datetime.now(tz=timezone.utc)


def is_allowed_file(filename: str):
    ALLOWED_EXTENSIONS = {"csv"}
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_date_string(date_text):
    try:
        if date_text != datetime.strptime(date_text, DATETIME_FORMATE_CODE).strftime(
            DATETIME_FORMATE_CODE
        ):
            raise ValueError("Invalid date input. Must be in format DD-MM-YYYY")
        return True
    except ValueError:
        return False


def value_is_true(value: str):
    return value.lower() == "true"


@cache
def generate_stock_fair_value(
    most_recent_close: float, most_recent_fear_greed_index: int
) -> float:
    if not isinstance(most_recent_close, float):
        raise ValueError("Recent close must be instance of float")
    if not isinstance(most_recent_fear_greed_index, int):
        raise ValueError("Index must be instance of int")
    return round(most_recent_close * ((100 - most_recent_fear_greed_index) / 100), 2)
