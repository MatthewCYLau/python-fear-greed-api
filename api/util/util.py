import logging
from flask import jsonify
from datetime import date, datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta, TU
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
import time
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


async def return_random_int(x: int) -> int:
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

    if current_pe_ratio < 0:
        return -1

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


def log_time(func):

    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        result = func(*args, **kwargs)
        end_time = time.perf_counter()
        logging.info(
            f"Function '{func.__name__}' took {end_time - start_time:.4f} seconds to execute."
        )
        return result

    return wrapper


@log_time
@shock
def predict_price_linear_regression(
    stock_symbol: str, data_years_ago: int, prediction_years_future: int
) -> Tuple[float]:
    try:
        data = yf.Ticker(stock_symbol)
        df = data.history(period=f"{data_years_ago}y")

        # Create a numerical representation of the time index
        model1 = create_stock_close_linear_regression_model(df)

        # Calculate the date one year in the future
        last_date = df.index[-1]
        future_date = last_date + pd.DateOffset(years=prediction_years_future)
        future_days = (future_date - df.index.min()).days

        # Predict the price for the future date
        future_price1 = model1.predict([[future_days]])[0]
        logging.info(f"Price prediction 1: {future_price1}")

        # Uses values.reshape
        model2 = create_stock_close_linear_regression_model(df, True)

        last_date = df.index[-1]
        future_date = last_date + pd.DateOffset(years=1)
        extended_index = pd.date_range(
            start=df.index[0], end=future_date, freq=df.index.freq
        )

        future_price2 = model2.predict(
            extended_index.values.astype(float).reshape(-1, 1)
        )[-1][0]

        logging.info(f"Price prediction 2: {future_price2}")
        prediction_result = statistics.mean([future_price1, future_price2])
        logging.info(f"Original result prediction result: {prediction_result}")

        return (prediction_result,)

    except Exception as e:
        logging.error(e)
        return 0


def create_stock_close_linear_regression_model(df, use_values_reshape: bool = False):

    if use_values_reshape:
        x = df.index
        y = df["Close"].values.reshape(-1, 1)

        lm = LinearRegression()
        model = lm.fit(x.values.reshape(-1, 1), y)

    else:
        df["Days"] = (df.index - df.index.min()).days

        # Prepare the data for the linear regression model
        x = df[["Days"]]
        y = df["Close"]

        # Create and train the linear regression model
        model = LinearRegression()
        model.fit(x, y)

    return model


def generate_monthly_mean_close_df(df: pd.DataFrame):

    logging.info(f"Index name: {df.index.name}")

    groupby_month_mean = df.groupby(pd.Grouper(freq="ME"))["Close"].mean()

    df_monthly_mean_sorted = groupby_month_mean.sort_index(ascending=True)

    df_monthly_mean_sorted.index = df_monthly_mean_sorted.index.strftime("%b %Y")

    df_monthly_mean_reset = df_monthly_mean_sorted.reset_index(name="Monthly Average")
    logging.info(f"Reset dataframe columns: {df_monthly_mean_reset.columns}")

    df_monthly_mean_reset["Monthly Average"] = df_monthly_mean_reset[
        "Monthly Average"
    ].apply(lambda x: float("{:.2f}".format(x)))

    max_monthly_average_close = df_monthly_mean_reset.loc[
        df_monthly_mean_reset["Monthly Average"].idxmax()
    ]
    logging.info(
        f"Max monthly average: {max_monthly_average_close['Date']} {max_monthly_average_close['Monthly Average']}"
    )

    min_monthly_average_close = df_monthly_mean_reset.loc[
        df_monthly_mean_reset["Monthly Average"].idxmin()
    ]
    logging.info(
        f"Minimum monthly average: {min_monthly_average_close['Date']} {min_monthly_average_close['Monthly Average']}"
    )

    current_month_year = datetime.today().strftime("%b %Y")
    df_current_month_mean = df_monthly_mean_reset[
        df_monthly_mean_reset["Date"] == current_month_year
    ]
    if len(df_current_month_mean):
        current_average_close = df_current_month_mean["Monthly Average"].values[0]
    else:
        previous_month_year = (datetime.today() - timedelta(days=30)).strftime("%b %Y")
        df_previous_month_mean = df_monthly_mean_reset[
            df_monthly_mean_reset["Date"] == previous_month_year
        ]
        current_average_close = df_previous_month_mean["Monthly Average"].values[0]

    logging.info(
        f"Current monthly average: {current_month_year} {current_average_close}"
    )

    return df_monthly_mean_reset


def check_asset_available(asset: str) -> bool:
    info = yf.Ticker(asset).history(period="7d", interval="1d")
    return len(info) > 0


def get_currency_impact_stock_return_df(
    stock_symbol: str, years_ago: int, currency: str
):
    stock_data = yf.download(stock_symbol, get_years_ago_formatted(int(years_ago)))[
        "Close"
    ]

    fx_ticker = f"{currency}USD=X"

    fx_data = yf.download(fx_ticker, get_years_ago_formatted(int(years_ago)))["Close"]
    df = pd.concat([stock_data, fx_data], axis=1).dropna()
    df.columns = ["Stock_Price_Local", "FX_Rate_USD_per_Local"]

    df["Local_Stock_Return"] = df["Stock_Price_Local"].pct_change()
    df["FX_Return"] = df["FX_Rate_USD_per_Local"].pct_change()

    df["Total_USD_Return"] = (1 + df["Local_Stock_Return"]) * (1 + df["FX_Return"]) - 1

    df["Cumulative_Local_Return"] = (1 + df["Local_Stock_Return"]).cumprod() - 1
    df["Cumulative_USD_Return"] = (1 + df["Total_USD_Return"]).cumprod() - 1
    return df


def generate_dividend_yield_df(stock_symbol: str, years_ago: int) -> pd.DataFrame:
    """
    Returns a DataFrame with:
      - Date
      - Close price
      - Annual dividends (TTM)
      - TTM dividend yield (%)
    """
    # ------------------------------------------------------------------
    # 1. Download price & dividend data
    # ------------------------------------------------------------------
    ticker = yf.Ticker(stock_symbol)

    # Historical close prices
    hist = ticker.history(period=f"{years_ago}y", auto_adjust=False)
    if hist.empty:
        raise ValueError(f"No data found for ticker {stock_symbol}")

    # Dividends (Series indexed by date)
    dividends = ticker.dividends

    df = hist[["Close"]].copy()

    # Resample dividends to daily frequency (forward-fill the amount)
    div_daily = dividends.resample("D").sum()
    df = df.join(div_daily.rename("Dividend"), how="left")
    df["Dividend"] = df["Dividend"].fillna(0)

    # Rolling sum of the last 365 days of dividends
    df["TTM_Dividend"] = df["Dividend"].rolling(window=365, min_periods=1).sum()

    # TTM yield
    df["TTM_Yield_%"] = (df["TTM_Dividend"] / df["Close"]) * 100

    df = df[
        [
            "Close",
            "Dividend",
            "TTM_Dividend",
            "TTM_Yield_%",
        ]
    ]
    df = df.round(2)

    return df


def get_tuesday_date_months_ago(months_ago: int):
    today = date.today()
    months_ago = today - relativedelta(months=months_ago)
    return (months_ago + relativedelta(weekday=TU(-1))).strftime(
        PANDAS_DF_DATE_FORMATE_CODE
    )


def log_utc_time_now():
    logging.info(
        f"{'UTC time now:':<20}{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
    )


def get_stock_price(symbol: str):
    stock = yf.Ticker(symbol)
    data = stock.history(period="1d")
    if data.empty:
        raise ValueError("Invalid stock symbol")
    return data["Close"].iloc[-1]


def get_portfolio_value(portfolio_list):
    stock_symbols = [item["stock_symbol"] for item in portfolio_list]
    tickers = yf.Tickers(" ".join(stock_symbols))

    total_value = 0.0

    for item in portfolio_list:
        stock_symbol = item["stock_symbol"]
        quantity = item["quantity"]

        current_price = tickers.tickers[stock_symbol].fast_info["last_price"]

        item_value = current_price * quantity
        total_value += item_value

        logging.info(
            f"{stock_symbol:<10} | ${current_price:>8.2f} | {quantity:>10} | ${item_value:>9.2f}"
        )

    return round(total_value, 2)


def get_user_portfolio_analysis_df(portfolio_data):

    df = pd.DataFrame(portfolio_data)

    stock_symbols = df["stock_symbol"].tolist() + ["^GSPC"]
    price_data = yf.download(stock_symbols, period="1y", progress=False)["Close"]

    df["current_price"] = df["stock_symbol"].apply(lambda x: price_data[x].iloc[-1])

    initial_prices = price_data.iloc[0]
    df["buy_price"] = df["stock_symbol"].map(initial_prices)

    df["market_value"] = df["quantity"] * df["current_price"]
    total_value = df["market_value"].sum()
    total_invested = (df["quantity"] * df["buy_price"]).sum()

    df["weight"] = df["market_value"] / total_value

    df["weight_pct"] = df["weight"].map(lambda x: f"{x:.2%}")

    portfolio_roi = ((total_value - total_invested) / total_invested) * 100

    sp500_start = initial_prices["^GSPC"]
    sp500_current = price_data.iloc[-1]["^GSPC"]
    sp500_roi = ((sp500_current - sp500_start) / sp500_start) * 100

    logging.info(f"Total Portfolio Value: ${total_value:,.2f}")
    logging.info(f"Portfolio ROI: {portfolio_roi:.2f}%")
    logging.info(f"S&P 500 ROI: {sp500_roi:.2f}%")
    logging.info(f"Alpha: {portfolio_roi - sp500_roi:.2f}%")

    return df


def get_portfolio_alpha(portfolio_roi: float, benchmark: str = "^GSPC"):
    data = yf.Ticker(benchmark)
    df = data.history(period="1y")
    sp500_start = df.iloc[0]["Close"]
    sp500_current = df.iloc[-1]["Close"]
    sp500_roi = ((sp500_current - sp500_start) / sp500_start) * 100
    return portfolio_roi - sp500_roi


def get_user_portfolio_roi_series(portfolio_data, benchmark: str = "^GSPC"):
    tickers = [item["stock_symbol"] for item in portfolio_data]
    quantities = {item["stock_symbol"]: item["quantity"] for item in portfolio_data}

    data = yf.download(tickers + [benchmark], period="1y")["Close"]

    portfolio_daily_values = data[tickers].mul(pd.Series(quantities), axis=1)
    total_portfolio_value = portfolio_daily_values.sum(axis=1)

    portfolio_roi = total_portfolio_value / total_portfolio_value.iloc[0]

    benchmark_roi = data[benchmark] / data[benchmark].iloc[0]

    return portfolio_roi, benchmark_roi
