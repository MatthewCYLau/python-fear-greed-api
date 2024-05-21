from datetime import datetime
from api.user.models import User
from api.alert.models import Alert


def test_new_user():
    user = User(
        "foo@bar.com",
        "password",
        "foo",
        False,
    )
    assert user.email == "foo@bar.com"
    assert user.name == "foo"


def test_new_alert():
    alert = Alert(
        index=40,
        note="foo",
        created_by="bar",
    )
    assert alert.view_count == 0
    assert type(alert.created) is datetime
