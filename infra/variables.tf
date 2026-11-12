variable "project" {
  description = "Prefix for resource names and the project tag."
  type        = string
  default     = "grocery-price-tracking"
}

variable "region" {
  description = "AWS region. Use the same one as your Databricks workspace."
  type        = string
  default     = "us-east-2"
}

variable "aws_profile" {
  description = "AWS CLI profile Terraform should use. Null uses the default credential chain (also what CI uses)."
  type        = string
  default     = null
}
