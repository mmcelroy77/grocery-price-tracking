output "state_bucket_name" {
  value = aws_s3_bucket.tfstate.bucket
}

output "release_user_name" {
  description = "Create an access key for this user by hand and store it as GitHub environment secrets."
  value       = aws_iam_user.release.name
}
