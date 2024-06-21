import os
from api import app


def test_ping():
    os.environ['CONFIG_TYPE'] = 'config.TestingConfig'
    flask_app = app

    with flask_app.test_client() as test_client:
        response = test_client.get('/ping')
        assert response.status_code == 200
        assert b"pong!" in response.data
