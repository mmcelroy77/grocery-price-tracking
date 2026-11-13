from types import SimpleNamespace

import pytest

from grocery_price_tracking.common import aws_auth
from grocery_price_tracking.common.aws_auth import (
    AwsCredentials,
    get_account_id,
    get_aws_credentials,
    s3a_spark_conf,
)


class FakeSession:
    def __init__(self, credentials=None):
        self._credentials = credentials
        self.clients = []

    def get_credentials(self):
        return self._credentials

    def client(self, name):
        self.clients.append(name)
        return SimpleNamespace(get_caller_identity=lambda: {"Account": "123456789012"})


def _fake_creds(token=None):
    frozen = SimpleNamespace(access_key="AKID", secret_key="SECRET", token=token)
    return SimpleNamespace(get_frozen_credentials=lambda: frozen)


@pytest.fixture
def use_session(monkeypatch):
    """Make the cached boto3 session (and account ID) come from a fake."""

    def install(session):
        monkeypatch.setattr(aws_auth.boto3, "Session", lambda: session)
        return session

    aws_auth._session.cache_clear()
    get_account_id.cache_clear()
    yield install
    aws_auth._session.cache_clear()
    get_account_id.cache_clear()


def test_get_aws_credentials(use_session):
    use_session(FakeSession(_fake_creds("TOKEN")))
    assert get_aws_credentials() == AwsCredentials("AKID", "SECRET", "TOKEN")


def test_get_aws_credentials_raises_when_missing(use_session):
    use_session(FakeSession(None))
    with pytest.raises(RuntimeError, match="No AWS credentials"):
        get_aws_credentials()


def test_get_account_id_uses_sts_and_caches(use_session):
    session = use_session(FakeSession())
    assert get_account_id() == "123456789012"
    assert get_account_id() == "123456789012"
    assert session.clients == ["sts"]


def test_credentials_repr_hides_secrets():
    text = repr(AwsCredentials("AKID", "SECRET", "TOKEN"))
    assert "SECRET" not in text and "TOKEN" not in text


def test_s3a_conf_static_keys():
    conf = s3a_spark_conf(AwsCredentials("AKID", "SECRET"), "us-east-2")
    assert conf["spark.hadoop.fs.s3a.aws.credentials.provider"].endswith(
        "SimpleAWSCredentialsProvider"
    )
    assert conf["spark.hadoop.fs.s3a.access.key"] == "AKID"
    assert conf["spark.hadoop.fs.s3a.secret.key"] == "SECRET"
    assert conf["spark.hadoop.fs.s3a.endpoint.region"] == "us-east-2"
    assert "spark.hadoop.fs.s3a.session.token" not in conf


def test_s3a_conf_session_token():
    conf = s3a_spark_conf(AwsCredentials("AKID", "SECRET", "TOKEN"), "us-east-2")
    assert conf["spark.hadoop.fs.s3a.aws.credentials.provider"].endswith(
        "TemporaryAWSCredentialsProvider"
    )
    assert conf["spark.hadoop.fs.s3a.session.token"] == "TOKEN"
