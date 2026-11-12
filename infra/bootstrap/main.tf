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
