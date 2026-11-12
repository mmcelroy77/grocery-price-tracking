variable "project" {
  description = "Prefix for resource names and the project tag."
  type        = string
  default     = "grocery-price-tracking"
}

variable "region" {
  description = "AWS region. Keep the same as ../variables.tf."
  type        = string
  default     = "us-east-2"
}

variable "aws_profile" {
  description = "AWS CLI profile to use. Null uses the default credential chain."
  type        = string
  default     = null
}
