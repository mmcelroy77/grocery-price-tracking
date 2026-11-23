output "bucket_name" {
  value = aws_s3_bucket.data.bucket
}

output "bucket_arn" {
  value = aws_s3_bucket.data.arn
}

output "ecr_repository_url" {
  description = "Where to push the job image (docker tag/push)."
  value       = aws_ecr_repository.job.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.jobs.name
}

output "task_definition_family" {
  value = aws_ecs_task_definition.job.family
}

output "task_network_configuration" {
  description = "Value for `aws ecs run-task --network-configuration` (default VPC subnets)."
  value = join("", [
    "awsvpcConfiguration={subnets=[${join(",", data.aws_subnets.default.ids)}],",
    "securityGroups=[${aws_security_group.job.id}],assignPublicIp=ENABLED}",
  ])
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.job.name
}
