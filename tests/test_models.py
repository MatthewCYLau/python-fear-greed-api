from datetime import datetime, timezone
from src.user.models import User

def test_new_user():
    user = User(
        "foo@bar.com",
        "password",
        "foo",
        False,
        created=datetime.now(timezone.utc),
        last_modified=datetime.now(timezone.utc),
    )
    assert user.email == "foo@bar.com"
    assert user.name == "foo"
