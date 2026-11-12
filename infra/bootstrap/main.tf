# One-time setup, applied locally with admin credentials. Creates what the GitHub Actions
# pipeline needs before it can run: a Terraform state bucket, the GitHub OIDC identity
# provider, and an IAM role. This config keeps its own local state (infra/bootstrap/terraform.tfstate,
# gitignored); keep that file, or re-import the resources if it is lost.

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
  account_id        = data.aws_caller_identity.current.account_id
  state_bucket_name = "${var.project}-${local.account_id}-tfstate"
  data_bucket_name  = "${var.project}-${local.account_id}-data"
  oidc_url          = "token.actions.githubusercontent.com"
}

# --- Terraform state bucket ---

resource "aws_s3_bucket" "tfstate" {
  bucket = local.state_bucket_name
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

# --- GitHub OIDC: lets workflows get short-lived AWS credentials without stored keys ---

resource "aws_iam_openid_connect_provider" "github" {
  url            = "https://${local.oidc_url}"
  client_id_list = ["sts.amazonaws.com"]
}

# Only this repo's jobs that run in the GitHub environment (the OIDC `sub` claim) may assume the role.
data "aws_iam_policy_document" "trust" {
  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_url}:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_url}:sub"
      values   = ["repo:${var.github_repo}:environment:${var.github_environment}"]
    }
  }
}

# --- Release role: used by .github/workflows/release.yml, behind the GitHub environment approval. ---
# Scoped to this project's resources (names must match infra/main.tf). Add statements here when infra/ starts managing new
# kinds of resources (otherwise the pipeline gets AccessDenied).

resource "aws_iam_role" "release" {
  name               = "${var.project}-github-release"
  assume_role_policy = data.aws_iam_policy_document.trust.json
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

resource "aws_iam_role_policy" "release" {
  name   = "release"
  role   = aws_iam_role.release.id
  policy = data.aws_iam_policy_document.release.json
}
