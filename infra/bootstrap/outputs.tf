output "state_bucket_name" {
  value = aws_s3_bucket.tfstate.bucket
}

output "release_role_arn" {
  description = "Set as the GitHub repository variable AWS_RELEASE_ROLE_ARN."
  value       = aws_iam_role.release.arn
}
