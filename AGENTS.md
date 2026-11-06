# Agent Instructions

Before starting any task in this repository:

1. Run `make agents/sync`. It writes the shared Plus3 IT instructions for this repository's tardigrade-ci version to `.agents/plus3it/AGENTS.md`.
2. Read `.agents/plus3it/AGENTS.md` and follow it together with this file. If the sync fails, tell the user, and don't guess the conventions.

These rules always apply, even without the shared instructions:

- Don't push, open pull requests, publish releases, or apply infrastructure changes unless the user asks. List those steps for a person in your final report.
- Don't edit files under `.agents/plus3it/`; they are generated and overwritten by the sync.

@.agents/plus3it/AGENTS.md

## Repository-specific

### Purpose

This Terraform module deploys a Lambda function that deletes the default CloudTrail trail, and its S3 bucket, in AWS accounts that are created in or invited to an AWS Organization. EventBridge rules for the `CreateAccountResult` and `InviteAccountToOrganization` events trigger the function. The main input is `project_name`, which prefixes the resource names; `event_types`, `cloudtrail_name_prefix`, `assume_role_name`, and `dry_run` (default `true`) control what runs. The module has no outputs.

### Module-specific files

- `src/delete_default_cloudtrail.py` — Source of the Lambda function, packaged by the module at plan time. It reads the account ID from the event and assumes the role named by `assume_role_name` in that account. It then finds the one trail whose name starts with `cloudtrail_name_prefix`, stops logging, deletes the trail, empties its S3 bucket, and deletes the bucket. When `dry_run` is true, it only logs what it would delete. It also has a command-line entry point.
- `src/requirements.txt` — Runtime packages for the Lambda function, installed when the module builds the package
- `tests/test_delete_default_cloudtrail/cloudtrail/` — Helper module that creates a test trail and bucket for the test scenario
