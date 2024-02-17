from api.user.models import User


def test_new_user():
    user = User(
        "foo@bar.com",
        "password",
        "foo",
        False,
    )
    assert user.email == "foo@bar.com"
    assert user.name == "foo"
