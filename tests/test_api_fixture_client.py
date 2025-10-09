import json
from dotenv import load_dotenv
import os
import pytest
import random
import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from api.common.constants import PANDAS_DF_DATE_FORMATE_CODE


config_file_path = "config/.env"
if os.path.exists(config_file_path):
    load_dotenv(config_file_path)


def test_ping_with_fixture(test_client):
    response = test_client.get("/ping")
    assert response.status_code == 200
    assert b"pong!" in response.data


def test_not_found_with_fixture(test_client):
    response = test_client.get("/foo")
    assert response.status_code == 404


def test_random_number_with_fixture(test_client):
    response = test_client.get("/random")
    assert response.status_code == 200
    assert b"random_num" in response.data
    assert isinstance(json.loads(response.data)["random_num"], int)


def test_async_with_fixture(test_client):
    response = test_client.get("/async")
    assert response.status_code == 200
    response_json = json.loads(response.data)
    assert isinstance(response_json, list)
    assert isinstance(response_json[0]["result"], int)


def test_records_export_csv_invalid_start_date(test_client):
    start_date = "FOO"
    response = test_client.post(
        f"/api/records/export-csv?startDate={start_date}&endDate=01-10-2023"
    )
    assert response.status_code == 400
    assert b"Invalid date input" in response.data


def test_records_export_csv_invalid_end_date(test_client):
    end_date = "FOO"
    response = test_client.post(
        f"/api/records/export-csv?startDate=01-10-2023&endDate={end_date}"
    )
    assert response.status_code == 400
    assert b"Invalid date input" in response.data


def test_get_auth_user_with_fixture_unauthorized(test_client):
    response = test_client.get("/api/auth")
    assert response.status_code == 401


def test_login_with_fixture_unauthorized(test_client):
    response = test_client.post(
        "/api/auth",
        data=json.dumps(dict(email="", password="")),
        content_type="application/json",
    )
    assert response.status_code == 401


def test_login_with_fixture_authorized(test_client):
    response = test_client.post(
        "/api/auth",
        data=json.dumps(
            dict(email="test@example.com", password=os.getenv("TEST_USER_PASSWORD"))
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "token" in response.json


def test_get_alerts_authorized(test_client):
    response = test_client.post(
        "/api/auth",
        data=json.dumps(
            dict(email="test@example.com", password=os.getenv("TEST_USER_PASSWORD"))
        ),
        content_type="application/json",
    )
    token = response.json.get("token")
    response = test_client.get(
        "/api/alerts",
        headers={"x-auth-token": token},
        content_type="application/json",
    )
    assert response.status_code == 200


@pytest.fixture(scope="module")
def create_alert_dict():
    payload_dict = {"index": random.randint(80, 99), "note": "Test alert"}
    return payload_dict


@pytest.fixture(scope="module")
def create_alert_dict_invalid():
    payload_dict = {"index": 101, "note": "Test alert"}
    return payload_dict


@pytest.fixture(scope="module")
def generate_auth_token(test_client):
    response = test_client.post(
        "/api/auth",
        data=json.dumps(
            dict(email="test@example.com", password=os.getenv("TEST_USER_PASSWORD"))
        ),
        content_type="application/json",
    )
    token = response.json.get("token")
    return token


@pytest.fixture(scope="module")
def sleep():
    sleep_seconds = random.uniform(20, 60)
    time.sleep(sleep_seconds)
    yield


def test_create_delete_alert_authorized(test_client, create_alert_dict):
    response = test_client.post(
        "/api/auth",
        data=json.dumps(
            dict(email="test@example.com", password=os.getenv("TEST_USER_PASSWORD"))
        ),
        content_type="application/json",
    )
    token = response.json.get("token")
    create_alert_response = test_client.post(
        "/api/alerts",
        headers={"x-auth-token": token},
        content_type="application/json",
        data=json.dumps(create_alert_dict),
    )
    assert create_alert_response.status_code == 201
    assert "alert_id" in create_alert_response.json

    delete_alert_response = test_client.delete(
        f'/api/alerts/{create_alert_response.json["alert_id"]}',
        headers={"x-auth-token": token},
        content_type="application/json",
    )
    assert delete_alert_response.status_code == 200


def test_create_alert_invalid_payload(test_client, create_alert_dict_invalid):
    response = test_client.post(
        "/api/auth",
        data=json.dumps(
            dict(email="test@example.com", password=os.getenv("TEST_USER_PASSWORD"))
        ),
        content_type="application/json",
    )
    token = response.json.get("token")

    create_alert_response = test_client.post(
        "/api/alerts",
        headers={"x-auth-token": token},
        content_type="application/json",
        data=json.dumps(create_alert_dict_invalid),
    )
    assert create_alert_response.status_code == 400


@pytest.fixture(scope="module")
def create_analysis_job_dict():
    payload_dict = {"stock": "TSLA", "targetFearGreedIndex": 45, "targetPeRatio": 40}
    return payload_dict


def test_create_delete_analysis_job_authorized(test_client, create_analysis_job_dict):
    response = test_client.post(
        "/api/auth",
        data=json.dumps(
            dict(email="test@example.com", password=os.getenv("TEST_USER_PASSWORD"))
        ),
        content_type="application/json",
    )
    token = response.json.get("token")
    create_analysis_job_response = test_client.post(
        "/api/analysis-jobs",
        headers={"x-auth-token": token},
        content_type="application/json",
        data=json.dumps(create_analysis_job_dict),
    )
    assert create_analysis_job_response.status_code == 200
    assert "analysisJobId" in create_analysis_job_response.json
    assert "messageId" in create_analysis_job_response.json

    time.sleep(60)

    delete_analysis_job_response = test_client.delete(
        f'/api/analysis-jobs/{create_analysis_job_response.json["analysisJobId"]}',
        headers={"x-auth-token": token},
        content_type="application/json",
    )
    assert delete_analysis_job_response.status_code == 200


def test_get_analysis_jobs_authorized(test_client, generate_auth_token):
    get_analysis_jobs_response = test_client.get(
        "/api/analysis-jobs",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert get_analysis_jobs_response.status_code == 200


def test_get_events_invalid_arguments(test_client, generate_auth_token):
    startDate = "foo"
    endDate = "bar"
    response = test_client.get(
        f"/api/events/me?startDate={startDate}&endDate={endDate}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_get_events(test_client, generate_auth_token):
    startDate = "01-01-2024"
    endDate = "01-01-2025"
    response = test_client.get(
        f"/api/events/me?startDate={startDate}&endDate={endDate}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200


def test_get_users_authorized(test_client, generate_auth_token):
    response = test_client.get(
        "/api/users",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200


def test_get_user_by_id_authorized(test_client, generate_auth_token):
    get_users_response = test_client.get(
        "/api/users",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    user_id = get_users_response.json[0].get("_id")
    get_user_response = test_client.get(
        f"/api/users/{user_id}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert get_user_response.status_code == 200


def test_get_records_authorized_valid_date(test_client, generate_auth_token):
    requested_date = "2024-11-08"
    response = test_client.get(
        f"/api/records?date={requested_date}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "index" in response.json
    assert "description" in response.json
    assert isinstance(response.json.get("index"), int)


def test_get_records_authorized_date_too_old(test_client, generate_auth_token):
    requested_date = (datetime.now() - relativedelta(days=500)).strftime(
        PANDAS_DF_DATE_FORMATE_CODE
    )
    response = test_client.get(
        f"/api/records?date={requested_date}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_generate_stock_plot_gcs_blob_invalid_roling_average(
    test_client, generate_auth_token
):
    stock_symbol = "SPY"
    rolling_average_days = 200
    response = test_client.post(
        f"/api/generate-stock-plot?stocks={stock_symbol}&rollingAverageDays={rolling_average_days}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_get_stock_analysis_authorized_valid_stock(
    test_client, generate_auth_token, sleep
):
    sleep
    stock_symbol = "AAPL"
    response = test_client.get(
        f"/api/analysis?stock={stock_symbol}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "close" in response.json
    assert isinstance(response.json.get("close"), float)
    assert "fairValue" in response.json
    assert isinstance(response.json.get("fairValue"), float)
    assert "peRatio" in response.json
    assert isinstance(response.json.get("peRatio"), float)


def test_get_stock_analysis_authorized_invalid_stock(
    test_client, generate_auth_token, sleep
):
    sleep
    stock_symbol = "FOO"
    response = test_client.get(
        f"/api/analysis?stock={stock_symbol}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 500


def test_export_stock_analysis_csv(test_client, sleep):
    sleep
    stock_symbol = "AAPL"
    response = test_client.post(f"/api/analysis/export-csv?stock={stock_symbol}")
    assert response.status_code == 200
    assert response.mimetype == "text/csv"


def test_generate_stock_plot_gcs_blob_invalid_years_ago(
    test_client, generate_auth_token
):
    stock_symbol = "SPY"
    years_ago = 5
    response = test_client.post(
        f"/api/generate-stock-plot?stocks={stock_symbol}&years={years_ago}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 400


def test_generate_stock_plot_gcs_blob_valid(test_client, generate_auth_token, sleep):
    sleep
    stock_symbol = "SPY"
    years_ago = 2
    response = test_client.post(
        f"/api/generate-stock-plot?stocks={stock_symbol}&years={years_ago}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "image_url" in response.json


def test_generate_stock_plot_gcs_blob_valid_forex(
    test_client, generate_auth_token, sleep
):
    sleep
    base_currency = "GBP"
    quote_currency = "USD"
    years_ago = 2
    response = test_client.post(
        f"/api/generate-stock-plot?years={years_ago}&baseCurrency={base_currency}&quoteCurrency={quote_currency}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "image_url" in response.json


def test_price_prediction_async_with_fixture(test_client):
    stock = "AAPL"
    runs_count = 3
    response = test_client.get(
        f"/api/analysis/price-prediction-async?stock={stock}&runsCount={runs_count}"
    )
    assert response.status_code == 200
    assert "pricePredictionMean" in response.json
    assert isinstance(response.json.get("pricePredictionMean"), float)


def test_generate_stock_mean_close(test_client, generate_auth_token, sleep):
    sleep
    stock = "AAPL"
    years = 1
    response = test_client.post(
        "/api/generate-stock-mean-close-plot",
        data=json.dumps({"stock": stock, "years": years}),
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "image_url" in response.json


def test_get_price_prediction_multiprocess(test_client, generate_auth_token, sleep):
    sleep
    stock = "AAPL"
    runs_count = 1
    response = test_client.get(
        f"/api/analysis/price-prediction-async?stock={stock}&runsCount={runs_count}",
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "pricePredictionMean" in response.json
    assert isinstance(response.json.get("pricePredictionMean"), float)
    assert isinstance(response.json.get("predictionRunCount"), int)
    assert response.json.get("predictionRunCount") == 1


def test_generate_stock_close_daily_return_plot_gcs_blob(
    test_client, generate_auth_token, sleep
):
    sleep
    stock = "AAPL"
    years = 1
    response = test_client.post(
        "/api/generate-stock-close-daily-return-plot",
        data=json.dumps({"stock": stock, "years": years}),
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "image_url" in response.json


def test_analyse_currency_impact_on_return(test_client, generate_auth_token, sleep):
    sleep
    stock = "AAPL"
    years = 1
    currency = "GBP"
    response = test_client.post(
        "/api/analyse-currency-impact",
        data=json.dumps({"stock": stock, "years": years, "currency": currency}),
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "currencyImpact" in response.json
    assert isinstance(response.json.get("currencyImpact"), float)


def test_generate_currency_impact_on_return_plot_gcs_blob(
    test_client, generate_auth_token, sleep
):
    sleep
    stock = "AAPL"
    years = 1
    currency = "GBP"
    response = test_client.post(
        "/api/generate-currency-impact-plot",
        data=json.dumps({"stock": stock, "years": years, "currency": currency}),
        headers={"x-auth-token": generate_auth_token},
        content_type="application/json",
    )
    assert response.status_code == 200
    assert "image_url" in response.json
