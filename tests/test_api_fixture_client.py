import json
from dotenv import load_dotenv
import os
import pytest
import random

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
