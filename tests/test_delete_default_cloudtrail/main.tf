locals {
  cloudtrail_name_prefix = "cloudtrail-${local.id}-"
  cloudtrail_suffix      = "test-deletion"

  id      = random_string.id.result
  project = "test-delete-ct-${local.id}"

  tags = {
    "project" = local.project
  }
}

module "test_cloudtrail" {
  source             = "./cloudtrail"
  cloudtrail_name    = "${local.cloudtrail_name_prefix}${local.cloudtrail_suffix}"
  cloudtrail_s3_name = "${local.cloudtrail_name_prefix}${local.cloudtrail_suffix}-bucket"
  tags               = local.tags
}

module "delete_default_cloudtrail" {
  source                 = "../../"
  project_name           = local.project
  assume_role_name       = aws_iam_role.assume_role.name
  cloudtrail_name_prefix = local.cloudtrail_name_prefix
  dry_run                = true
  error_not_found        = true
  log_level              = "DEBUG"
  tags                   = local.tags
}


data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_iam_policy_document" "iam_cloudtrail" {
  statement {
    actions = [
      "cloudtrail:DescribeTrails",
      "cloudtrail:GetTrail",
    ]

    resources = [
      "*"
    ]
  }

  statement {
    actions = [
      "cloudtrail:DeleteTrail",
      "cloudtrail:StopLogging"
    ]

    resources = [
      module.test_cloudtrail.cloudtrail_arn
    ]
  }
  statement {
    actions = [
      "s3:ListBucket",
      "s3:GetObject",
      "s3:DeleteObject",
      "s3:DeleteBucket"
    ]

    resources = [
      module.test_cloudtrail.s3_bucket_arn,
      "${module.test_cloudtrail.s3_bucket_arn}/*"
    ]
  }
}

resource "aws_iam_role" "assume_role" {
  name = "${local.project}-delete-default-cloudtrail-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        "Sid" : "AssumeRoleCrossAccount",
        "Effect" : "Allow",
        "Principal" : {
          "AWS" : "arn:${data.aws_partition.current.partition}:iam::${data.aws_caller_identity.current.account_id}:root"
        },
        "Action" : "sts:AssumeRole"
      }
    ]
  })

  inline_policy {
    name   = local.project
    policy = data.aws_iam_policy_document.iam_cloudtrail.json
  }
}

resource "random_string" "id" {
  length  = 6
  upper   = false
  special = false
  numeric = false
}
