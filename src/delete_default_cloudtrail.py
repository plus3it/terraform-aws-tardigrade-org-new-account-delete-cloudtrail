"""Delete Cloudtrail.

Purpose:
    Delete the cloudtrail with preifx CLOUDTRAIL_NAME_PREFIX environment variable
Environment Variables:
    LOG_LEVEL: (optional): sets the level for function logging
            valid input: critical, error, warning, info (default), debug
    CLOUDTRAIL_NAME_PREFIX: cloudtrail name to delete (default: cloudtrail-)
    DRY_RUN: (optional): true or false, defaults to true
    ASSUME_ROLE_NAME: Name of role to assume
"""
from argparse import ArgumentParser, RawDescriptionHelpFormatter
import collections
import logging
import os
import sys

import boto3
from aws_assume_role_lib import assume_role, generate_lambda_session_name
from botocore.exceptions import ClientError

# Standard logging config
DEFAULT_LOG_LEVEL = logging.INFO
LOG_LEVELS = collections.defaultdict(
    lambda: DEFAULT_LOG_LEVEL,
    {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
    },
)
CLOUDTRAIL_NAME_PREFIX = os.getenv("CLOUDTRAIL_NAME_PREFIX", "cloudtrail-")
ERROR_NOT_FOUND = bool(os.getenv("ERROR_NOT_FOUND", "true").lower() == "true")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"
ASSUME_ROLE_NAME = os.environ.get("ASSUME_ROLE_NAME", "OrganizationAccountAccessRole")

# Lambda initializes a root logger that needs to be removed in order to set a
# different logging config
root = logging.getLogger()
if root.handlers:
    for handler in root.handlers:
        root.removeHandler(handler)

logging.basicConfig(
    format="%(asctime)s.%(msecs)03dZ [%(name)s][%(levelname)-5s]: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    level=LOG_LEVELS[os.environ.get("LOG_LEVEL", "").lower()],
)

log = logging.getLogger(__name__)

# Get the Lambda session and clients
SESSION = boto3.Session()


class NoCloudtrailsFoundError(Exception):
    """Error raised when there are no cloudtrails matching the name/pattern."""


class MultipleCloudtrailsFoundError(Exception):
    """Error raised when there are mutliple cloudtrails matching the name/pattern."""


class DeleteDefaultCloudtrailError(Exception):
    """All errors raised by DeleteDefaultCloudtrail Lambda."""


def lambda_handler(event, context):  # pylint: disable=unused-argument
    """Delete the default cloudtrail and s3 bucket."""
    log.debug("AWS Event:%s", event)

    account_id = get_account_id(event)

    assume_role_arn = f"arn:{get_partition()}:iam::{account_id}:role/{ASSUME_ROLE_NAME}"

    delete_cloudtrail_resources(assume_role_arn, account_id)


def delete_cloudtrail_resources(assume_role_arn, account_id):
    """Delete cloudtrail resources from either a lambda or main method."""
    cloudtrail_client, s3_client = get_boto3_clients(assume_role_arn, account_id)

    cloudtrail = get_cloudtrail(cloudtrail_client, CLOUDTRAIL_NAME_PREFIX)

    if cloudtrail:
        if not DRY_RUN:
            delete_cloudtrail(cloudtrail["Trail"]["TrailARN"], cloudtrail_client)
            delete_s3_bucket(cloudtrail["Trail"]["S3BucketName"], s3_client)
        else:
            log.warning(
                "NOT ARMED: Cloudtrail ARN: %s, S3 Bucket Name: %s",
                cloudtrail["Trail"]["TrailARN"],
                cloudtrail["Trail"]["S3BucketName"],
            )
    else:
        log.warning("Cloudtrail %s not found.", CLOUDTRAIL_NAME_PREFIX)


def get_cloudtrail(client, prefix):
    """Find the cloudtrail by prefix."""
    # Get the cloudtrail by prefix
    matching_trails = []
    try:
        cloudtrails = client.describe_trails(trailNameList=[])
        for trail in cloudtrails["trailList"]:
            if trail["Name"].startswith(prefix):
                matching_trails.append(trail["Name"])

        if len(matching_trails) > 1:
            multiple_found_error = (
                f"Multiple ({len(matching_trails)}) "
                f"cloudtrails found: {prefix}, {matching_trails}"
            )
            log.error(multiple_found_error)
            raise MultipleCloudtrailsFoundError(multiple_found_error)

        if len(matching_trails) == 0:
            none_found_error = f"No cloudtrail found for prefix {prefix}"
            if ERROR_NOT_FOUND:
                log.error(none_found_error)
                raise NoCloudtrailsFoundError(none_found_error)
            log.warning(none_found_error)
            return None

        return client.get_trail(Name=matching_trails[0])

    except ClientError as err:
        log.error("Error getting cloudtrail %s", err)
        raise DeleteDefaultCloudtrailError(
            f"Error getting cloudtrail by prefix {prefix}"
        ) from err


def delete_cloudtrail(cloudtrail_arn, client):
    """Stop and Delete the cloudtrail for the arn provided."""
    # Stop logging to the trail
    client.stop_logging(Name=cloudtrail_arn)
    # Delete the trail
    client.delete_trail(Name=cloudtrail_arn)
    log.debug("Cloudtrail %s has been deleted.", cloudtrail_arn)


def delete_s3_bucket(bucket_name, client):
    """Delete the s3 bucket by name."""
    # Delete all s3 objects first
    delete_s3_objects(bucket_name, client)
    # Delete the s3 bucket
    client.delete_bucket(Bucket=bucket_name)
    log.debug("S3 bucket %s has been deleted.", bucket_name)


def get_boto3_clients(assume_role_arn, account_id):
    """Get the cloudtrail and s3 clients."""
    # Assume the session
    assumed_role_session = get_assumed_role_session(account_id, assume_role_arn)
    # Create the cloudtrail and s3 clients
    cloudtrail_client = assumed_role_session.client("cloudtrail")
    s3_client = assumed_role_session.client("s3")
    return cloudtrail_client, s3_client


def delete_s3_objects(bucket_name, client):
    """Delete all objects from the s3 bucket."""
    # Get all objects from the s3 bucket
    objects = client.list_objects_v2(Bucket=bucket_name)["Contents"]
    # Delete all objects from the s3 bucket
    for obj in objects:
        client.delete_object(Bucket=bucket_name, Key=obj["Key"])

    log.debug("All objects from s3 bucket %s have been deleted.", bucket_name)


def get_new_account_id(event):
    """Return account id for new account events."""
    return event["detail"]["serviceEventDetails"]["createAccountStatus"]["accountId"]


def get_invite_account_id(event):
    """Return account id for invite account events."""
    return event["detail"]["requestParameters"]["target"]["id"]


def get_account_id(event):
    """Return account id for supported events."""
    event_name = event["detail"]["eventName"]
    get_account_id_strategy = {
        "CreateAccountResult": get_new_account_id,
        "InviteAccountToOrganization": get_invite_account_id,
    }
    return get_account_id_strategy[event_name](event)


def get_assumed_role_session(account_id, role_arn):
    """Get boto3 session."""
    function_name = os.environ.get(
        "AWS_LAMBDA_FUNCTION_NAME", os.path.basename(__file__)
    )

    role_session_name = generate_lambda_session_name(function_name)

    # Assume the session
    assumed_role_session = assume_role(
        SESSION, role_arn, RoleSessionName=role_session_name, validate=False
    )
    # do stuff with the assumed role using assumed_role_session
    log.debug(
        "Assumed identity for account %s is %s",
        account_id,
        assumed_role_session.client("sts").get_caller_identity()["Arn"],
    )
    return assumed_role_session


def get_partition():
    """Return AWS partition."""
    sts = boto3.client("sts")
    return sts.get_caller_identity()["Arn"].split(":")[1]


def cli_main(target_account_id, assume_role_arn=None, assume_role_name=None):
    """Process cli assume_role_name arg and pass to main."""
    log.debug(
        "CLI - target_account_id=%s assume_role_arn=%s assume_role_name=%s",
        target_account_id,
        assume_role_arn,
        assume_role_name,
    )

    if assume_role_name:
        assume_role_arn = (
            f"arn:{get_partition()}:iam::{target_account_id}:role/{assume_role_name}"
        )
        log.info("assume_role_arn for provided role name is '%s'", assume_role_arn)

    main(target_account_id, assume_role_arn)


def main(target_account_id, assume_role_arn):
    """Assume role and delete cloudtrail resources."""
    log.debug(
        "Main identity is %s",
        SESSION.client("sts").get_caller_identity()["Arn"],
    )

    delete_cloudtrail_resources(
        assume_role_arn,
        target_account_id,
    )

    if DRY_RUN:
        log.debug("Dry Run listed all resources that would be deleted")
    else:
        log.debug("Deleted cloudtrail associated s3 bucket/objects")


if __name__ == "__main__":

    def create_args():
        """Return parsed arguments."""
        parser = ArgumentParser(
            formatter_class=RawDescriptionHelpFormatter,
            description="""
Delete Default Cloudtrail for provided target account.

Supported Environment Variables:
    'LOG_LEVEL': defaults to 'info'
        - set the desired log level ('error', 'warning', 'info' or 'debug')

    'DRY_RUN': defaults to 'true'
        - set whether actions should be simulated or live
        - value of 'true' (case insensitive) will be simulated.

    CLOUDTRAIL_NAME_PREFIX: cloudtrail name prefix to delete (default: cloudtrail-)
""",
        )
        required_args = parser.add_argument_group("required named arguments")
        required_args.add_argument(
            "--target-account-id",
            required=True,
            type=str,
            help="Account number to delete default cloudtrail resources in",
        )
        mut_x_group = parser.add_mutually_exclusive_group(required=True)
        mut_x_group.add_argument(
            "--assume-role-arn",
            type=str,
            help="ARN of IAM role to assume in the target account (case sensitive)",
        )
        mut_x_group.add_argument(
            "--assume-role-name",
            type=str,
            help="Name of IAM role to assume in the target account (case sensitive)",
        )

        return parser.parse_args()

    sys.exit(cli_main(**vars(create_args())))
