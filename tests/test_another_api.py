def test_ping_with_fixture(test_client):
    response = test_client.get('/ping')
    assert response.status_code == 200
    assert b"pong!" in response.data

def test_not_found_with_fixture(test_client):
    response = test_client.get('/foo')
    assert response.status_code == 404
