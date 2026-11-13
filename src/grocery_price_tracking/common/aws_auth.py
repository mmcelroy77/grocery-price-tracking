"""Resolve AWS credentials and turn them into Spark S3A config.

boto3 resolves credentials, so every method the AWS CLI supports also works here:
env vars, ~/.aws/credentials profiles, `aws login`, SSO. Set AWS_PROFILE to use a
non-default profile. The resolved keys are handed to Hadoop's S3A connector as static
(or session) credentials.
"""

from dataclasses import dataclass, field
from functools import cache

import boto3

_S3A = "org.apache.hadoop.fs.s3a"


@dataclass(frozen=True)
class AwsCredentials:
    """AWS credentials resolved for one process. Secrets are hidden from repr().

    Attributes:
    access_key -- AWS access key ID.
    secret_key -- AWS secret access key.
    token -- session token for temporary credentials, or None for long-term keys.
    """

    access_key: str
    secret_key: str = field(repr=False)
    token: str | None = field(default=None, repr=False)


@cache
def _session() -> boto3.Session:
    """Return the process-wide boto3 session, so credentials resolve only once.

    Returns:
    a boto3 session using the standard AWS credential chain.
    """
    return boto3.Session()


def get_aws_credentials() -> AwsCredentials:
    """Resolve credentials via the standard AWS chain (honours AWS_PROFILE).

    Temporary credentials (SSO, `aws login`, assumed roles) are snapshotted, so a
    job that outlives them needs to be restarted.

    Returns:
    the current credentials.

    Raises:
    RuntimeError -- if no credentials are configured.
    """
    credentials = _session().get_credentials()
    if credentials is None:
        raise RuntimeError(
            "No AWS credentials found. Sign in with `aws login` or `aws configure`, "
            "or set AWS_PROFILE."
        )
    frozen = credentials.get_frozen_credentials()
    return AwsCredentials(frozen.access_key, frozen.secret_key, frozen.token)


@cache
def get_account_id() -> str:
    """Look up the AWS account ID of the current credentials.

    Calls STS GetCallerIdentity once; later calls return the cached value.

    Returns:
    the 12-digit account ID.

    Raises:
    botocore.exceptions.NoCredentialsError -- if no credentials are configured.
    """
    return _session().client("sts").get_caller_identity()["Account"]


def s3a_spark_conf(credentials: AwsCredentials, region: str) -> dict[str, str]:
    """Build the Spark config that lets s3a:// (and s3://) paths use credentials.

    Spark redacts keys matching secret/token in the UI and logs by default.

    Arguments:
    credentials -- credentials to pass to Hadoop's S3A connector.
    region -- AWS region of the bucket(s) being accessed.

    Returns:
    Spark config keys (spark.hadoop.fs.s3a.*) mapped to their values.
    """
    provider = (
        "TemporaryAWSCredentialsProvider"
        if credentials.token
        else "SimpleAWSCredentialsProvider"
    )
    conf = {
        "spark.hadoop.fs.s3a.aws.credentials.provider": f"{_S3A}.{provider}",
        "spark.hadoop.fs.s3a.access.key": credentials.access_key,
        "spark.hadoop.fs.s3a.secret.key": credentials.secret_key,
        "spark.hadoop.fs.s3a.endpoint.region": region,
        # Let s3:// URIs (the form AWS and Databricks use) go through S3A too.
        "spark.hadoop.fs.s3.impl": f"{_S3A}.S3AFileSystem",
    }
    if credentials.token:
        conf["spark.hadoop.fs.s3a.session.token"] = credentials.token
    return conf
