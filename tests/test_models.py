import pytest
from datetime import datetime
from api.user.models import User
from api.alert.models import Alert
from api.record.models import Record
from api.exception.models import BadRequestException


def test_new_user():
    user = User(
        "foo@bar.com",
        "password",
        "foo",
        False,
    )
    assert user.email == "foo@bar.com"
    assert user.name == "foo"
    assert not user.isEmailVerified
    assert user.avatarImageUrl == ""


def test_new_alert():
    alert = Alert(
        index=40,
        note="foo",
        created_by="bar",
    )
    assert alert.view_count == 0
    assert alert.index == 40
    assert type(alert.created) is datetime


@pytest.fixture(scope="module")
def new_record():
    record = Record(42)
    return record


def test_new_record_with_fixture(new_record):
    assert new_record.index == 42
    assert type(new_record.creatd) is str


@pytest.fixture(scope="module")
def new_bad_request_exception():
    bad_request_exception = BadRequestException("Custom exception message", 400)
    return bad_request_exception


def test_new_bad_request_exceptions_with_fixture(new_bad_request_exception):
    assert new_bad_request_exception.status_code == 400
