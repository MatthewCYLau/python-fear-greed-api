import pytest
from datetime import datetime
from api.user.models import User, TestUserType, UserType, Currency
from api.alert.models import Alert
from api.common.models import BaseModel
from api.record.models import Record
from api.analysis.models import AnalysisJob
from api.exception.models import BadRequestException, UnauthorizedException
from api.util.util import (
    generate_df_from_csv,
)


def test_new_user():
    user = User(
        "foo@bar.com", "password", "foo", False, regularContributionAmount=210.50
    )
    assert user.email == "foo@bar.com"
    assert user.name == "foo"
    assert not user.isEmailVerified
    assert user.avatarImageUrl == ""
    assert user.regularContributionAmount == 210.50
    assert user.currency == Currency.GBP.name


def test_new_user_invalid_regular_contribution():
    with pytest.raises(TypeError):
        _ = User(
            "foo@bar.com", "password", "foo", False, regularContributionAmount="foo"
        )


def test_new_user_invalid_currency():
    with pytest.raises(TypeError):
        _ = User(
            "foo@bar.com",
            "password",
            "foo",
            False,
            regularContributionAmount=10,
            currency="FOO",
        )


def test_new_user_valid_currency():
    user = User(
        "foo@bar.com",
        "password",
        "foo",
        False,
        regularContributionAmount=210.50,
        currency=Currency["EUR"],
    )
    assert user.currency == Currency.EUR.name


def test_new_alert():
    alert = Alert(
        index=40,
        note="foo",
        created_by="bar",
    )
    assert alert.view_count == 0
    assert alert.index == 40
    assert not alert.have_actioned
    assert type(alert.created) is datetime


def test_new_analysis_job():
    analysis_job = AnalysisJob(
        stock_symbol="AAPL",
        created_by="bar",
    )
    assert analysis_job.stock_symbol == "AAPL"
    assert not analysis_job.complete


@pytest.fixture(scope="module")
def new_record():
    record = Record(42)
    return record


def test_new_record_with_fixture(new_record):
    assert new_record.index == 42
    assert type(new_record.created) is str


@pytest.fixture(scope="module")
def new_bad_request_exception():
    bad_request_exception = BadRequestException("Custom exception message", 400)
    return bad_request_exception


def test_new_bad_request_exceptions_with_fixture(new_bad_request_exception):
    assert new_bad_request_exception.status_code == 400


@pytest.fixture(scope="module")
def new_unauthorized_exception():
    unauthorized_exception = UnauthorizedException("Unauthorized request")
    return unauthorized_exception


def test_new_unauthorized_exception_with_fixture(new_unauthorized_exception):
    assert new_unauthorized_exception.status_code == 401


def test_user_type():
    test_user = TestUserType(UserType.INDIVIDUAL_INVESTOR)
    assert test_user.userType == "INDIVIDUAL_INVESTOR"


def test_new_base_model():
    base = BaseModel()
    assert type(base.created) is datetime
    assert base.created == base.last_modified


def test_import_from_dataframe():
    df = generate_df_from_csv("data/example.csv")
    records_imported = Record.import_from_dataframe(df)
    assert records_imported == 2
