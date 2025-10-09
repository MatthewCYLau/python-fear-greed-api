import pytest
import pandas as pd
import numpy as np
import time
import yfinance as yf
from api.util.cloud_storage_connector import CloudStorageConnector
from api.util.util import (
    return_dupliucated_items_in_list,
    is_valid_sector,
    validate_date_string,
    generate_stock_fair_value,
    is_allowed_file,
    value_is_true,
    return_union_set,
    return_random_int,
    generate_df_from_csv,
    return_delta,
    generate_figure_blob_filename,
    validate_date_string_for_pandas_df,
    predict_price_linear_regression,
    generate_monthly_mean_close_df,
    check_asset_available,
    get_currency_impact_stock_return_df,
)
from api.auth.auth import validate_google_oauth_token


def test_return_duplicated_items_in_list_one_duplicate():
    list_with_duplicated_items_foo = ["foo", "bar", "foo"]
    assert return_dupliucated_items_in_list(list_with_duplicated_items_foo) == {"foo"}


def test_return_duplicated_items_in_list_two_duplicates():
    list_with_duplicated_items_foo_bar = ["foo", "bar", "foo", "bar"]
    assert return_dupliucated_items_in_list(list_with_duplicated_items_foo_bar) == {
        "foo",
        "bar",
    }


def test_return_duplicated_items_in_list_no_duplicates():
    list_without_duplicated_items = ["bar", "foo"]
    assert return_dupliucated_items_in_list(list_without_duplicated_items) == set()


def test_is_valid_sector():
    assert is_valid_sector("Financial Services")
    assert not is_valid_sector("Foo")


def test_validate_date_string():
    assert not validate_date_string("06-22-2023")
    assert validate_date_string("26-06-2023")


def test_validate_date_string_for_pandas_df():
    assert not validate_date_string_for_pandas_df("2024-25-03")
    assert validate_date_string_for_pandas_df("2024-03-03")


def test_generate_stock_fair_value():
    assert (
        generate_stock_fair_value(
            most_recent_close=191.04,
            most_recent_fear_greed_index=64,
            current_pe_ratio=29.71,
        )
        == 60.28
    )

    assert (
        generate_stock_fair_value(
            most_recent_close=195.58,
            most_recent_fear_greed_index=45,
            current_pe_ratio=24.31,
        )
        == 107.27
    )


def test_generate_stock_fair_value_value_error():
    with pytest.raises(ValueError):
        generate_stock_fair_value("foo", 34, 10.00)


def test_is_allowed_filename():
    assert is_allowed_file("foo.csv")
    assert not is_allowed_file("foo.txt")


def test_value_is_true():
    assert value_is_true("True")
    assert value_is_true("true")
    assert not value_is_true("False")
    assert not value_is_true("false")


async def test_return_random_int():
    assert isinstance(await return_random_int(x=1), int)


def test_return_union_set():
    assert return_union_set(["foo", "bar"], ["bar", "fooo"]) == {"foo", "bar", "fooo"}


def test_generate_df_from_csv():
    df = generate_df_from_csv("data/example.csv")
    assert "Index" in df.columns
    assert df["Index"].dtype, pd.Int64Dtype()
    assert df.index.inferred_type == "datetime64"


def test_return_delta():
    assert return_delta(10.54, 30.23) == -0.65
    assert return_delta(40.54, 30.23) == 0.34


def test_generate_figure_blob_filename():
    assert "pie" in generate_figure_blob_filename("pie")
    assert "scatter" in generate_figure_blob_filename("scatter")


@pytest.fixture
def cloud_storage_connector():
    return CloudStorageConnector("my_bucket")


def test_cloud_storage_connector(cloud_storage_connector):
    assert cloud_storage_connector.bucket_name == "my_bucket"
    assert type(cloud_storage_connector.storage_client)


def test_validate_google_oauth_token_invalid_token():
    valid, user_id, email, name = validate_google_oauth_token("foo")
    assert not valid
    assert not user_id
    assert not email
    assert not name


def test_predict_price_linear_regression():
    prediction = predict_price_linear_regression("TSLA", 1, 1)
    time.sleep(1 * 60)  # prevent rate limiting
    assert isinstance(prediction, tuple)


def test_predict_price_linear_regression_function_name():
    assert predict_price_linear_regression.__name__ == "predict_price_linear_regression"


def test_generate_monthly_mean_close_df():
    data = yf.Ticker("AAPL")
    df = data.history(period="1y")
    monthly_mean_close_df = generate_monthly_mean_close_df(df)
    assert "Monthly Average" in monthly_mean_close_df.columns
    assert "Date" in monthly_mean_close_df.columns
    assert monthly_mean_close_df["Monthly Average"].dtype, pd.Float64Dtype


def test_generate_monthly_mean_close_df_random_df():
    today = pd.to_datetime("today")
    dates = pd.date_range(today, periods=100)
    df = pd.DataFrame(data=np.random.randn(100, 1), index=dates, columns=["Close"])
    df.index.name = "Date"
    monthly_mean_close_df = generate_monthly_mean_close_df(df)
    assert "Monthly Average" in monthly_mean_close_df.columns
    assert monthly_mean_close_df["Monthly Average"].dtype, pd.Float64Dtype


def test_check_asset_available():
    assert check_asset_available("AAPL")
    assert not check_asset_available("FOO")


def test_get_currency_impact_stock_return_df():
    stock = "AAPL"
    years = 1
    currency = "GBP"
    df = get_currency_impact_stock_return_df(stock, years, currency)
    assert "Cumulative_Local_Return" in df.columns
    assert "Cumulative_USD_Return" in df.columns
    assert df["Cumulative_USD_Return"].dtype, pd.Float64Dtype
