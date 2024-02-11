from flask import Blueprint, request, make_response
from api.db.setup import db
from api.util.util import generate_response
from datetime import datetime
import pandas as pd
import numpy as np

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

    # drop redundant columns
    df = df.drop(columns=["_id", "creatd"])

    # re-name column
    df.rename(columns={"index": "fear_greed_index"}, inplace=True)

    # remove rows with empty created timestamp
    df["created"].replace("", np.nan, inplace=True)
    df.dropna(subset=["created"], inplace=True)

    # set created column as data frame index
    df["created"] = pd.to_datetime(df["created"], format="ISO8601", utc=True)
    df = df.set_index("created")

    response = make_response(df.to_csv())
    response.headers["Content-Disposition"] = (
        f"attachment; filename={datetime.today().strftime('%Y-%m-%d')}.csv"
    )
    response.mimetype = "text/csv"
    return response
