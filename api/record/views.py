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
    min_index = int(request.args["min"]) if "min" in request.args else 0
    max_index = int(request.args["max"]) if "max" in request.args else 100

    start_date = request.args["startDate"] if "startDate" in request.args else None
    end_date = request.args["endDate"] if "endDate" in request.args else None

    if start_date and end_date:
        records = list(
            db["records"].find(
                {
                    "created": {
                        "$gte": datetime.strptime(start_date, "%d-%m-%Y")
                        .date()
                        .isoformat(),
                        "$lt": datetime.strptime(end_date, "%d-%m-%Y")
                        .date()
                        .isoformat(),
                    }
                }
            )
        )
    else:
        records = list(db["records"].find())

    df = pd.DataFrame(records)

    # drop redundant columns
    df = df.drop(columns=["_id"])
    if "creatd" in df.columns:
        df = df.drop(columns=["creatd"])

    # re-name column
    df.rename(columns={"index": "fear_greed_index"}, inplace=True)

    # remove rows with empty created timestamp
    df["created"] = df["created"].replace("", np.nan)
    df.dropna(subset=["created"], inplace=True)

    # set created column as data frame index
    df["created"] = pd.to_datetime(df["created"], format="ISO8601", utc=True)
    df = df.set_index("created")

    df = df.astype({"fear_greed_index": int})

    filtered_df = df.loc[
        (df["fear_greed_index"] >= min_index) & (df["fear_greed_index"] <= max_index)
    ]

    response = make_response(filtered_df.to_csv())
    response.headers["Content-Disposition"] = (
        f"attachment; filename={datetime.today().strftime('%Y-%m-%d')}.csv"
    )
    response.mimetype = "text/csv"
    return response
