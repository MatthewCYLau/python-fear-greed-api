from flask import Blueprint, request, make_response, jsonify
from api.common.constants import DATETIME_FORMATE_CODE, PANDAS_DF_DATE_FORMATE_CODE
from api.db.setup import db
from api.util.util import (
    generate_response,
    validate_date_string,
    is_allowed_file,
    generate_df_from_csv,
    generate_figure_blob_filename,
    validate_date_string_for_pandas_df,
)
from api.util.cloud_storage_connector import CloudStorageConnector
from api.exception.models import BadRequestException
from api.record.models import Record
from api.auth.auth import auth_required
from datetime import datetime, timedelta
from api.rate_limiter.rate_limiter import limiter
from dateutil.relativedelta import relativedelta
from google.cloud import storage
import logging
import yaml
import os
import io
import json
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns


matplotlib.use("agg")


bp = Blueprint("records", __name__)
limiter.limit("25/minute")(bp)

with open(
    os.path.dirname(os.path.dirname(__file__)) + "/config/columns.yaml", "r"
) as f:
    yaml_content = yaml.safe_load(f)

with open(
    os.path.dirname(os.path.dirname(__file__)) + "/config/gcp_config.json"
) as gcp_config_json:
    gcp_config = json.load(gcp_config_json)
ASSETS_PLOTS_BUCKET_NAME = gcp_config["ASSETS_PLOTS_BUCKET_NAME"]
CHART_LABELS = ["Extreme greed", "Greed", "Neutral", "Fear", "Extreme fear"]


@bp.route("/records", methods=(["GET"]))
@auth_required
def get_records(_):
    if request.args.get("date"):
        record_date = request.args["date"]

        if not validate_date_string_for_pandas_df(record_date):
            raise BadRequestException(
                "Invalid date input. Must be in format YYYY-MM-DD", status_code=400
            )

        now = datetime.now()
        if (
            now - datetime.strptime(record_date, PANDAS_DF_DATE_FORMATE_CODE)
        ).days > 365:
            one_year_ago = now - relativedelta(days=365)
            raise BadRequestException(
                f"{record_date} is too far behind! Oldest date is one year ago from current time {one_year_ago.strftime(PANDAS_DF_DATE_FORMATE_CODE)}",
                status_code=400,
            )
        logging.info(f"Getting record for {record_date}")
        filtered_df = _generate_filtered_dataframe()
        filtered_df["created_date"] = filtered_df.index.date
        logging.info(filtered_df.tail())

        logging.info(f"{'Max index:':<20}{filtered_df['fear_greed_index'].max()}")
        logging.info(f"{'Min index:':<20}{filtered_df['fear_greed_index'].min()}")
        logging.info(
            f"{'Mean index:':<20}{'{:.2f}'.format(filtered_df['fear_greed_index'].mean())}"
        )

        filtered_series = filtered_df.loc[record_date:record_date, "fear_greed_index"]
        logging.info(filtered_series)
        filtered_df_iloc = filtered_df.loc[
            record_date:record_date, ["fear_greed_index", "description"]
        ]
        logging.info(filtered_df_iloc)
        if not len(filtered_series):
            return jsonify({"message": "Record for date not found"}), 404
        return jsonify(
            {
                "date": record_date,
                "index": int(
                    filtered_series.iloc[0]
                ),  # or int(filtered_series.values[0])
                "description": str(filtered_df_iloc.iloc[0]["description"]),
            }
        )

    count = int(request.args["count"]) if "count" in request.args else 0
    sort_direction = (
        1 if "order" in request.args and request.args["order"] == "asc" else -1
    )
    records = list(db["records"].find().sort("created", sort_direction).limit(count))
    return generate_response(records)


@bp.route("/records-count", methods=(["GET"]))
def get_records_count_bin():
    pipeline = [
        {"$project": {"_id": 0, "indexNumber": {"$toInt": "$index"}}},
        {
            "$project": {
                "indexLowerBound": {
                    "$subtract": ["$indexNumber", {"$mod": ["$indexNumber", 10]}]
                }
            }
        },
        {"$group": {"_id": "$indexLowerBound", "count": {"$sum": 1}}},
        {"$sort": {"_id": -1}},
    ]
    res = db["records"].aggregate(pipeline)
    return jsonify(list(res))


@bp.route("/records/export-csv", methods=(["POST"]))
def get_records_csv():
    filtered_df = _generate_filtered_dataframe()
    mean_index = filtered_df.loc[:, "fear_greed_index"].mean()
    logging.info(f"Mean index is {mean_index:.2f}")

    logging.info(
        filtered_df.groupby([filtered_df.index.strftime("%b %Y")])["fear_greed_index"]
        .mean()
        .reset_index(name="Monthly Average")
    )

    logging.info(f"Unique description values: {filtered_df['description'].unique()}")

    neutral_values_df = (
        filtered_df.groupby("description")
        .agg({"fear_greed_index": lambda x: list(x)})
        .filter(items=["Neutral"], axis=0)
    )

    logging.info(
        f"Neutral index values: {neutral_values_df['fear_greed_index'].values[0]}"
    )

    most_common_description_series = (
        filtered_df["description"].value_counts()[:1].sort_values(ascending=False)
    )
    most_common_description = most_common_description_series.index[0]
    most_common_description_count = most_common_description_series.loc[
        most_common_description
    ]

    logging.info(
        f"Most common description {most_common_description} has count {most_common_description_count}"
    )

    response = make_response(filtered_df.to_csv())
    response.headers["Content-Disposition"] = (
        f"attachment; filename={datetime.today().strftime(DATETIME_FORMATE_CODE)}.csv"
    )
    response.mimetype = "text/csv"
    return response


@bp.route("/records/upload-csv", methods=(["POST"]))
@auth_required
def upload_records_csv(_):
    file = request.files.get("file")

    if not file or not is_allowed_file(file.filename):
        raise BadRequestException("Please upload a CSV file", status_code=400)

    try:
        df = pd.read_csv(
            file, encoding="utf-8", index_col=["Date"], parse_dates=["Date"]
        )
    except Exception as e:
        raise BadRequestException(f"Failed to read CSV {e}", status_code=400)
    if "Index" in df.columns:
        logging.info("CSV has required columns.")
    logging.info(
        f"Count of records: {len(df.index)} Start date: {df.index.min().strftime(DATETIME_FORMATE_CODE)} End date: {df.index.max().strftime(DATETIME_FORMATE_CODE)}"
    )

    first_row_date = df.index[0]
    first_row_fear_greed_index_value = df.loc[first_row_date, "Index"]
    last_row_fear_greed_index_value = df.loc[df.index[-1], "Index"]
    logging.info(
        f"First row with date {first_row_date.strftime(DATETIME_FORMATE_CODE)} has index value: {first_row_fear_greed_index_value}"
    )

    return jsonify(
        {
            "recordsCount": len(df.index),
            "startDate": df.index.min(),
            "startDateIndexValue": int(first_row_fear_greed_index_value),
            "endDate": df.index.max(),
            "endDateIndexValue": int(last_row_fear_greed_index_value),
        }
    )


@bp.route("/records/import-from-csv", methods=(["POST"]))
@auth_required
def import_records_from_csv(_):
    object_url = request.get_json()["objectUrl"]
    storage_client = storage.Client()
    blob_name = object_url.split("/")[-1]
    bucket = storage_client.bucket("python-fear-greed-assets-uploads")
    blob = bucket.blob(blob_name)
    data = blob.download_as_bytes()
    df = generate_df_from_csv(io.BytesIO(data))
    records_imported = Record.import_from_dataframe(df)
    return jsonify(
        {
            "recordsImported": records_imported,
            "recordsCount": len(df.index),
            "startDate": df.index.min(),
            "endDate": df.index.max(),
        }
    )


@bp.route("/records/generate-plot", methods=(["POST"]))
@auth_required
def generate_plot_gcs_blob(_):
    chart_type = request.args["chartType"] if "chartType" in request.args else "scatter"
    bins_size = request.args["binSize"] if "binSize" in request.args else 5

    try:
        assert bins_size.isdigit() and int(bins_size) in (3, 4, 5)
    except AssertionError as e:
        logging.error(e)
        raise BadRequestException("Invalid bin size", status_code=400)

    df = _generate_filtered_dataframe()

    plt.figure(figsize=(10, 6))

    if chart_type == "scatter":
        sns.scatterplot(
            x=df.index, y=df["fear_greed_index"], color="blue", label="Index"
        )
        plt.title("Fear & Greed Index Scatter Plot", fontsize=14)
        plt.xlabel("Created", fontsize=12)
        plt.ylabel("Index", fontsize=12)

    elif chart_type == "histogram":
        n, x, _ = plt.hist(df["fear_greed_index"], bins=int(bins_size), histtype="step")
        bin_centers = 0.5 * (x[1:] + x[:-1])
        plt.plot(bin_centers, n)
        plt.title("Fear & Greed Index Histogram", fontsize=12)
        plt.xlabel("Index", fontsize=12)
        plt.ylabel("Count", fontsize=12)

    elif chart_type == "pie":
        description_counts = df["description"].value_counts()
        description_proportions = description_counts / description_counts.sum()
        plt.pie(
            description_proportions,
            labels=CHART_LABELS,
            autopct="%1.1f%%",
        )
        plt.title("Distribution of index by labels")

    elif chart_type == "bar":
        description_counts = df["description"].value_counts()
        plt.bar(
            CHART_LABELS,
            description_counts,
        )
        plt.xlabel("Index", fontsize=12)
        plt.ylabel("Count", fontsize=12)
        plt.title("Distribution of index by labels")

    else:
        return jsonify({"message": f"Invalid chart type {chart_type}"}), 500

    fig_to_upload = plt.gcf()
    cloud_storage_connector = CloudStorageConnector(
        bucket_name=ASSETS_PLOTS_BUCKET_NAME
    )
    file_name = generate_figure_blob_filename(chart_type)
    blob_public_url = cloud_storage_connector.upload_pyplot_figure(
        fig_to_upload, file_name
    )
    return jsonify({"image_url": blob_public_url}), 200


def _generate_filtered_dataframe():
    min_index = int(request.args["min"]) if "min" in request.args else 0
    max_index = int(request.args["max"]) if "max" in request.args else 100

    start_date = (
        request.args["startDate"]
        if "startDate" in request.args
        else (datetime.today() - relativedelta(years=1)).strftime(DATETIME_FORMATE_CODE)
    )
    end_date = (
        request.args["endDate"]
        if "endDate" in request.args
        else datetime.today().strftime(DATETIME_FORMATE_CODE)
    )

    dates_input = [start_date, end_date]

    if (
        start_date
        and end_date
        and not all([validate_date_string(i) for i in dates_input])
    ):
        raise BadRequestException(
            "Invalid date input. Must be in format DD-MM-YYYY", status_code=400
        )

    if datetime.strptime(end_date, DATETIME_FORMATE_CODE) > datetime.today():
        raise BadRequestException("End date cannot be after today", status_code=400)

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

    if not records:
        raise BadRequestException("No records found for date range", status_code=400)

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

    # also fill NaN values using an interpolation method
    df.interpolate(method="linear", axis=1)

    bins = (0, 25, 45, 55, 75, 100)
    group_names = tuple(yaml_content["columns"])
    df["description"] = pd.cut(df["fear_greed_index"], bins, labels=group_names)

    df_value_counts_description = df.value_counts(["description"]).reset_index(
        name="count"
    )
    for _, row in df_value_counts_description.iterrows():
        description = row["description"]
        count = row["count"]
        logging.info(f"{description} has count {count}")

    return df.loc[
        (df["fear_greed_index"] >= min_index) & (df["fear_greed_index"] <= max_index)
    ]


def _generate_random_dataframe():
    dates = pd.date_range(
        (datetime.today() - timedelta(days=10)).strftime("%Y-%m-%d"), periods=10
    )

    values = np.random.randint(1, 100, size=10)
    return pd.DataFrame({"Date": dates, "Value": values})
