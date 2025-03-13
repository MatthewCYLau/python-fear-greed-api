import pytest
import pandas as pd
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


# @pytest.fixture
# def cloud_storage_connector():
#     return CloudStorageConnector("my_bucket")


# def test_cloud_storage_connector(cloud_storage_connector):
#     assert cloud_storage_connector.bucket_name == "my_bucket"
#     assert type(cloud_storage_connector.storage_client)


def test_validate_google_oauth_token_invalid_token():
    valid, user_id, email, name = validate_google_oauth_token("foo")
    assert not valid
    assert not user_id
    assert not email
    assert not name
