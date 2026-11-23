# Runs jobs: each run is one Fargate task that runs the image built from ../Dockerfile and
# exits. Started by hand for now (see README.md); a schedule comes later.
#
# Cost: nothing runs between jobs. A one-minute run costs about a cent, and there is no
# NAT gateway because the task gets a public IP in a default-VPC subnet (outbound only).

locals {
  # Created by hand (see README.md), never by Terraform, so the secret values stay out of
  # state. The ARNs are built from the names; no data source reads the values.
  kroger_secrets = {
    KROGER_CLIENT_ID     = "/${var.project}/kroger/client_id"
    KROGER_CLIENT_SECRET = "/${var.project}/kroger/client_secret"
  }
  kroger_secret_arns = {
    for env_name, name in local.kroger_secrets :
    env_name => "arn:aws:ssm:${var.region}:${data.aws_caller_identity.current.account_id}:parameter${name}"
  }
}

# --- Image repository ---

resource "aws_ecr_repository" "job" {
  name = var.project
  # Lets `terraform destroy` remove the repository together with its images.
  force_delete = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "job" {
  repository = aws_ecr_repository.job.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

# --- Cluster and logs ---

resource "aws_ecs_cluster" "jobs" {
  name = var.project
}

resource "aws_cloudwatch_log_group" "job" {
  name              = "/ecs/${var.project}"
  retention_in_days = 14
}

# --- Network: default VPC, outbound HTTPS only ---

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
  filter {
    name   = "default-for-az"
    values = ["true"]
  }
}

resource "aws_security_group" "job" {
  name        = "${var.project}-job"
  description = "Job tasks: outbound HTTPS only (Kroger API, S3, ECR, SSM, CloudWatch)."
  vpc_id      = data.aws_vpc.default.id
}

resource "aws_vpc_security_group_egress_rule" "job_https" {
  security_group_id = aws_security_group.job.id
  description       = "HTTPS to anywhere"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}

# --- Roles ---

data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

# Used by ECS itself, before the job starts: pull the image, write logs, read the secrets.
resource "aws_iam_role" "job_execution" {
  name               = "${var.project}-job-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "job_execution" {
  role       = aws_iam_role.job_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "job_execution_secrets" {
  statement {
    sid       = "KrogerSecrets"
    actions   = ["ssm:GetParameters"]
    resources = values(local.kroger_secret_arns)
  }
}

resource "aws_iam_role_policy" "job_execution_secrets" {
  name   = "kroger-secrets"
  role   = aws_iam_role.job_execution.name
  policy = data.aws_iam_policy_document.job_execution_secrets.json
}

# Used by the job's own code (boto3 finds these credentials by itself): the data bucket only.
resource "aws_iam_role" "job_task" {
  name               = "${var.project}-job-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

data "aws_iam_policy_document" "job_task" {
  statement {
    sid = "DataBucket"
    actions = [
      "s3:GetObject",
      "s3:PutObject",
      "s3:DeleteObject",
      "s3:AbortMultipartUpload",
      "s3:ListMultipartUploadParts",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:GetBucketLocation",
    ]
    resources = [
      aws_s3_bucket.data.arn,
      "${aws_s3_bucket.data.arn}/*",
    ]
  }
}

resource "aws_iam_role_policy" "job_task" {
  name   = "data-bucket"
  role   = aws_iam_role.job_task.name
  policy = data.aws_iam_policy_document.job_task.json
}

# --- Task ---

resource "aws_ecs_task_definition" "job" {
  family                   = var.project
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 1024
  memory                   = 4096 # Spark's driver heap is 2 GB (spark.driver.memory)
  execution_role_arn       = aws_iam_role.job_execution.arn
  task_role_arn            = aws_iam_role.job_task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name      = "job"
    image     = "${aws_ecr_repository.job.repository_url}:${var.image_tag}"
    essential = true
    secrets = [
      for env_name, arn in local.kroger_secret_arns : { name = env_name, valueFrom = arn }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.job.name
        "awslogs-region"        = var.region
        "awslogs-stream-prefix" = "job"
      }
    }
  }])
}
