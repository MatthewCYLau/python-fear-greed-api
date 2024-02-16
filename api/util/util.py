from flask import jsonify
from datetime import datetime, timezone
import pytz
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


def get_current_time_gb():
    GB = pytz.timezone("Europe/London")
    return datetime.now(timezone.utc).astimezone(GB).isoformat()


def validate_date_string(date_text):
    try:
        if date_text != datetime.strptime(date_text, "%d-%m-%Y").strftime("%d-%m-%Y"):
            raise ValueError
        return True
    except ValueError:
        return False
