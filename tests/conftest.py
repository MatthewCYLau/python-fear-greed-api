import os
import pytest
from api import app


@pytest.fixture(scope='module')
def test_client():
    os.environ['CONFIG_TYPE'] = 'config.TestingConfig'
    flask_app = app

    with flask_app.test_client() as testing_client:
        with flask_app.app_context():
            yield testing_client 
