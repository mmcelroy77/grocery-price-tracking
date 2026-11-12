terraform {
  required_version = ">= 1.6"

  # State lives in the bucket created by infra/bootstrap. Locking uses an S3 lock file.
  backend "s3" {
    bucket       = "grocery-price-tracking-063280429352-tfstate"
    key          = "infra/terraform.tfstate"
    region       = "us-east-2"
    use_lockfile = true
  }

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

# Bucket names are global, so the account ID keeps this one unique.
resource "aws_s3_bucket" "data" {
  bucket = "${var.project}-${data.aws_caller_identity.current.account_id}-data"
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}
