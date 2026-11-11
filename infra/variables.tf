variable "project" {
  description = "Prefix for resource names and the project tag."
  type        = string
  default     = "grocery-price-tracking"
}

variable "region" {
  description = "AWS region. Use the same one as your Databricks workspace."
  type        = string
  default     = "us-west-2"
}

variable "aws_profile" {
  description = "AWS CLI profile (SSO or access keys) Terraform should use."
  type        = string
  default     = "default"
}
