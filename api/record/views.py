from flask import Blueprint, request, make_response
from api.db.setup import db
from api.util.util import generate_response
from datetime import datetime
import pandas as pd
import logging

bp = Blueprint("records", __name__)


@bp.route("/records", methods=(["GET"]))
def get_records():
    count = int(request.args["count"]) if "count" in request.args else 0
    sort_direction = (
        1 if "order" in request.args and request.args["order"] == "asc" else -1
    )
    records = list(db["records"].find().sort("created", sort_direction).limit(count))
    return generate_response(records)


@bp.route("/records/export-csv", methods=(["POST"]))
def get_records_csv():
    records = list(db["records"].find())
    df = pd.DataFrame(records)
    logging.info(f"Old headers: {df.columns}")
    df = df.drop(columns=["_id", "creatd"])
    logging.info(f"New headers: {df.columns}")
    response = make_response(df.to_csv())
    response.headers["Content-Disposition"] = (
        f"attachment; filename={datetime.today().strftime('%Y-%m-%d')}.csv"
    )
    response.mimetype = "text/csv"
    return response
