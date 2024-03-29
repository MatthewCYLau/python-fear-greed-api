import pytest
from api.util.util import (
    return_dupliucated_items_in_list,
    is_valid_sector,
    validate_date_string,
    generate_stock_fair_value,
)


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
    assert is_valid_sector("Financial Services") == True
    assert is_valid_sector("Foo") == False


def test_validate_date_string():
    assert validate_date_string("06-22-2023") == False
    assert validate_date_string("26-06-2023") == True


def test_generate_stock_fair_value():
    assert generate_stock_fair_value(100.12, 80) == 20.02
    assert generate_stock_fair_value(80.21, 34) == 52.94


def test_generate_stock_fair_value_value_error():
    with pytest.raises(ValueError):
        generate_stock_fair_value("foo", 34)
