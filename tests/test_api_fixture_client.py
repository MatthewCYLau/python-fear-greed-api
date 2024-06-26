import json

def test_ping_with_fixture(test_client):
    response = test_client.get('/ping')
    assert response.status_code == 200
    assert b"pong!" in response.data

def test_not_found_with_fixture(test_client):
    response = test_client.get('/foo')
    assert response.status_code == 404

def test_random_number_with_fixture(test_client):
    response = test_client.get('/random')
    assert response.status_code == 200
    assert b"random_num" in response.data
    assert isinstance(json.loads(response.data)['random_num'], int)

def test_async_with_fixture(test_client):
    response = test_client.get('/async')
    assert response.status_code == 200
    response_json = json.loads(response.data)
    assert isinstance(response_json, list)
    assert isinstance(response_json[0]['result'], int)

def test_records_export_csv_invalid_start_date(test_client):
    start_date = "FOO"
    response = test_client.post(f'/api/records/export-csv?startDate={start_date}&endDate=01-10-2023')
    assert response.status_code == 400
    assert b"Invalid date input" in response.data
