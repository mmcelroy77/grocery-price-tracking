# One-time setup, applied locally with admin credentials: the S3 bucket holding Terraform state for ../ and
# the IAM user the release workflow runs as. Keeps its own local state (gitignored; keep the file or
# re-import). The user's access key is created by hand (see ../README.md) so it stays out of state.
# GitHub OIDC would avoid long-lived keys but an SCP blocks it on the Free plan (see git history, 2c161b3).

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile

  default_tags {
    tags = {
      project    = var.project
      managed_by = "terraform"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id       = data.aws_caller_identity.current.account_id
  data_bucket_name = "${var.project}-${local.account_id}-data"
}

# --- Terraform state bucket (name must match the backend in ../main.tf) ---

resource "aws_s3_bucket" "tfstate" {
  bucket = "${var.project}-${local.account_id}-tfstate"
}

resource "aws_s3_bucket_public_access_block" "tfstate" {
  bucket                  = aws_s3_bucket.tfstate.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "tfstate" {
  bucket = aws_s3_bucket.tfstate.id
  versioning_configuration {
    status = "Enabled"
  }
}

# --- Release user: used by .github/workflows/release.yml (key stored as GitHub environment secrets) ---
# Scoped to this project's resources. Add statements when infra/ manages new kinds of resources.

resource "aws_iam_user" "release" {
  name = "${var.project}-github-release"
}

data "aws_iam_policy_document" "release" {
  statement {
    sid     = "DataBucket"
    actions = ["s3:*"]
    resources = [
      "arn:aws:s3:::${local.data_bucket_name}",
      "arn:aws:s3:::${local.data_bucket_name}/*",
    ]
  }

  statement {
    sid       = "StateBucketList"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.tfstate.arn]
  }

  statement {
    sid       = "StateObjects"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.tfstate.arn}/*"]
  }
}

resource "aws_iam_user_policy" "release" {
  name   = "release"
  user   = aws_iam_user.release.name
  policy = data.aws_iam_policy_document.release.json
}

# The job's permissions (infra/jobs.tf) are a managed policy because a user's inline policies
# are limited to 2048 bytes in total, and the policy above already uses most of that.
data "aws_iam_policy_document" "release_job" {
  statement {
    sid       = "EcrToken"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid       = "EcrRepository"
    actions   = ["ecr:*"]
    resources = ["arn:aws:ecr:${var.region}:${local.account_id}:repository/${var.project}"]
  }

  statement {
    sid = "EcsCluster"
    actions = [
      "ecs:CreateCluster",
      "ecs:DeleteCluster",
      "ecs:DescribeClusters",
      "ecs:UpdateCluster",
      "ecs:TagResource",
      "ecs:UntagResource",
      "ecs:ListTagsForResource",
    ]
    resources = ["arn:aws:ecs:${var.region}:${local.account_id}:cluster/${var.project}"]
  }

  # Task definitions can't be limited by resource when they are registered.
  statement {
    sid = "EcsTaskDefinitions"
    actions = [
      "ecs:RegisterTaskDefinition",
      "ecs:DeregisterTaskDefinition",
      "ecs:DeleteTaskDefinitions",
      "ecs:DescribeTaskDefinition",
      "ecs:TagResource",
      "ecs:UntagResource",
      "ecs:ListTagsForResource",
    ]
    resources = ["*"]
  }

  statement {
    sid = "LogGroup"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy",
      "logs:TagResource",
      "logs:UntagResource",
      "logs:ListTagsForResource",
      "logs:ListTagsLogGroup",
    ]
    resources = [
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/ecs/${var.project}",
      "arn:aws:logs:${var.region}:${local.account_id}:log-group:/ecs/${var.project}:*",
    ]
  }

  statement {
    sid       = "LogGroupsList"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"]
  }

  # Only roles named <project>-job-*, only for ECS tasks, and only the managed policy the
  # job execution role needs. The release user can't create or pass any other role.
  statement {
    sid = "JobRoles"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:PutRolePolicy",
      "iam:GetRolePolicy",
      "iam:DeleteRolePolicy",
    ]
    resources = ["arn:aws:iam::${local.account_id}:role/${var.project}-job-*"]
  }

  statement {
    sid       = "JobRoleManagedPolicies"
    actions   = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
    resources = ["arn:aws:iam::${local.account_id}:role/${var.project}-job-*"]
    condition {
      test     = "ArnEquals"
      variable = "iam:PolicyARN"
      values   = ["arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"]
    }
  }

  statement {
    sid       = "PassJobRoles"
    actions   = ["iam:PassRole"]
    resources = ["arn:aws:iam::${local.account_id}:role/${var.project}-job-*"]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      # ECS tasks use the execution and task roles. Scheduler uses the scheduler role.
      values = ["ecs-tasks.amazonaws.com", "scheduler.amazonaws.com"]
    }
  }

  # The daily schedule (infra/schedule.tf). Only schedules named <project>-job-*.
  statement {
    sid = "Schedule"
    actions = [
      "scheduler:CreateSchedule",
      "scheduler:UpdateSchedule",
      "scheduler:DeleteSchedule",
      "scheduler:GetSchedule",
    ]
    resources = ["arn:aws:scheduler:${var.region}:${local.account_id}:schedule/default/${var.project}-job-*"]
  }

  statement {
    sid = "NetworkRead"
    actions = [
      "ec2:DescribeAccountAttributes",
      "ec2:DescribeVpcs",
      "ec2:DescribeSubnets",
      "ec2:DescribeRouteTables",
      "ec2:DescribeVpcAttribute",
      "ec2:DescribeSecurityGroups",
      "ec2:DescribeSecurityGroupRules",
      "ec2:DescribeNetworkInterfaces",
      "ec2:DescribeTags",
    ]
    resources = ["*"]
  }

  statement {
    sid = "SecurityGroups"
    actions = [
      "ec2:CreateSecurityGroup",
      "ec2:DeleteSecurityGroup",
      "ec2:AuthorizeSecurityGroupEgress",
      "ec2:RevokeSecurityGroupEgress",
      "ec2:ModifySecurityGroupRules",
      "ec2:CreateTags",
      "ec2:DeleteTags",
    ]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "aws:RequestedRegion"
      values   = [var.region]
    }
  }
}

resource "aws_iam_policy" "release_job" {
  name   = "${var.project}-release-job"
  policy = data.aws_iam_policy_document.release_job.json
}

resource "aws_iam_user_policy_attachment" "release_job" {
  user       = aws_iam_user.release.name
  policy_arn = aws_iam_policy.release_job.arn
}
