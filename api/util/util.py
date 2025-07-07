import logging
from flask import jsonify
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta
from typing import List, Tuple
from api.common.constants import DATETIME_FORMATE_CODE, PANDAS_DF_DATE_FORMATE_CODE
import asyncio
import pandas as pd
import random
import json
import pytz
import yfinance as yf
from sklearn.linear_model import LinearRegression
import statistics
from functools import wraps


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


def validate_date_string_for_pandas_df(date_text):
    try:
        if date_text != datetime.strptime(
            date_text, PANDAS_DF_DATE_FORMATE_CODE
        ).strftime(PANDAS_DF_DATE_FORMATE_CODE):
            raise ValueError("Invalid date input. Must be in format YYYY-MM-DD")
        return True
    except ValueError:
        return False


def value_is_true(value: str):
    return value.lower() == "true"


def return_union_set(first_list: List[int], second_list: List[int]):
    return set(first_list) | set(second_list)


async def return_random_int(*, x: int) -> int:
    await asyncio.sleep(3)
    return random.randint(1, 10) * x


def generate_stock_fair_value(
    most_recent_close: float,
    most_recent_fear_greed_index: int,
    current_pe_ratio: float,
    target_fear_greed_index: int = 40,
    target_pe_ratio: int = 15,
) -> float:
    if not isinstance(most_recent_close, float) or not isinstance(
        current_pe_ratio, float
    ):
        raise ValueError("Recent close and current PE ratio must be instance of float")
    if not isinstance(most_recent_fear_greed_index, int) or not isinstance(
        target_fear_greed_index, int
    ):
        raise ValueError("Fear and greed index must be instance of int")
    return round(
        most_recent_close
        * (target_pe_ratio / current_pe_ratio)
        * (target_fear_greed_index / most_recent_fear_greed_index),
        2,
    )


def generate_df_from_csv(data):
    date_cols = [
        "Date",
    ]
    return pd.read_csv(
        data,
        sep=",",
        header=0,
        parse_dates=date_cols,
        index_col=["Date"],
        dayfirst=True,
    )


def return_delta(fair_value: int, most_recent_close: int) -> float:
    return float("{:.2f}".format((fair_value - most_recent_close) / most_recent_close))


def generate_figure_blob_filename(chart_type: str) -> str:
    GB = pytz.timezone("Europe/London")
    timestamp = datetime.now(timezone.utc).astimezone(GB).strftime("%Y%m%d%H%M%S")
    return f"{timestamp}-{chart_type}.png"


def get_years_ago_formatted(years: int = 1) -> str:
    current_date = datetime.today()
    one_year_ago = current_date - relativedelta(years=years)
    return one_year_ago.strftime("%Y-%m-%d")


def shock(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        (original_result,) = func(*args, **kwargs)
        if not isinstance(original_result, (int, float)):
            raise TypeError("Input must be a number (int or float).")

        max_difference = 0.10 * abs(original_result)
        random_diff = random.uniform(-max_difference, max_difference)
        adjusted_value = original_result + random_diff
        return (adjusted_value,)

    return wrapper


@shock
def predict_price_linear_regression(
    stock_symbol: str, data_years_ago: int, prediction_years_future: int
) -> Tuple[float]:
    try:
        data = yf.Ticker(stock_symbol)
        df = data.history(period=f"{data_years_ago}y")

        # Create a numerical representation of the time index
        df["Days"] = (df.index - df.index.min()).days

        # Prepare the data for the linear regression model
        x = df[["Days"]]
        y = df["Close"]

        # Create and train the linear regression model
        model = LinearRegression()
        model.fit(x, y)

        # Calculate the date one year in the future
        last_date = df.index[-1]
        future_date = last_date + pd.DateOffset(years=prediction_years_future)
        future_days = (future_date - df.index.min()).days

        # Predict the price for the future date
        future_price1 = model.predict([[future_days]])[0]
        logging.info(f"Price prediction 1: {future_price1}")

        # Uses values.reshape
        x = df.index
        y = df["Close"].values.reshape(-1, 1)

        lm = LinearRegression()
        model = lm.fit(x.values.reshape(-1, 1), y)

        last_date = df.index[-1]
        future_date = last_date + pd.DateOffset(years=1)
        extended_index = pd.date_range(
            start=df.index[0], end=future_date, freq=df.index.freq
        )

        future_price2 = lm.predict(extended_index.values.astype(float).reshape(-1, 1))[
            -1
        ][0]

        logging.info(f"Price prediction 2: {future_price2}")
        prediction_result = statistics.mean([future_price1, future_price2])
        logging.info(f"Original result prediction result: {prediction_result}")

        return (prediction_result,)

    except Exception as e:
        logging.error(e)
        return 0


def generate_monthly_mean_close_df(df: pd.DataFrame):

    df_groupby_month_mean = df.groupby(pd.Grouper(freq="ME"))["Close"].mean()

    df_monthly_mean_sorted = df_groupby_month_mean.sort_index(ascending=False)

    df_monthly_mean_sorted.index = df_monthly_mean_sorted.index.strftime("%b %Y")

    df_monthly_mean_reset = df_monthly_mean_sorted.reset_index(name="Monthly Average")

    df_monthly_mean_reset["Monthly Average"] = df_monthly_mean_reset[
        "Monthly Average"
    ].apply(lambda x: float("{:.2f}".format(x)))

    max_monthly_average_close = df_monthly_mean_reset.loc[
        df_monthly_mean_reset["Monthly Average"].idxmax()
    ]
    logging.info(
        f"Max monthly average: {max_monthly_average_close['Date']} {max_monthly_average_close['Monthly Average']}"
    )
    return df_monthly_mean_reset
