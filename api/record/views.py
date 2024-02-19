from flask import Blueprint, request, make_response
from api.common.constants import DATETIME_FORMATE_CODE
from api.db.setup import db
from api.util.util import generate_response, validate_date_string
from api.exception.models import BadRequestException
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

    dates_input = [start_date, end_date]

    if (
        start_date
        and end_date
        and not all([validate_date_string(i) for i in dates_input])
    ):
        raise BadRequestException(
            "Invalid date input. Must be in format DD-MM-YYYY", status_code=400
        )

    if start_date and end_date:
        records = list(
            db["records"].find(
                {
                    "created": {
                        "$gte": datetime.strptime(start_date, DATETIME_FORMATE_CODE)
                        .date()
                        .isoformat(),
                        "$lt": datetime.strptime(end_date, DATETIME_FORMATE_CODE)
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

    bins = [0, 25, 45, 55, 75, 100]
    group_names = ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]
    df["description"] = pd.cut(df["fear_greed_index"], bins, labels=group_names)

    filtered_df = df.loc[
        (df["fear_greed_index"] >= min_index) & (df["fear_greed_index"] <= max_index)
    ]

    response = make_response(filtered_df.to_csv())
    response.headers["Content-Disposition"] = (
        f"attachment; filename={datetime.today().strftime(DATETIME_FORMATE_CODE)}.csv"
    )
    response.mimetype = "text/csv"
    return response
