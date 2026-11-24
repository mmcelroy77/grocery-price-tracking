# Runs the job every day: EventBridge Scheduler starts one Fargate task from the task definition in
# jobs.tf. Running the job twice in a day is harmless: the Bronze write replaces that day's partition.

locals {
  # The task definition without a revision number, so the schedule always runs the newest revision.
  # Built from the family, which is a configured value and so known at plan time, instead of using the
  # resource's own `arn_without_revision`: that is only known after apply, and the resource is replaced
  # on every Release with a new commit, so the plan would list spurious "changes" to the schedule and
  # its role policy every time. Using the family keeps the dependency on the task definition.
  job_task_definition_family_arn = "arn:aws:ecs:${var.region}:${data.aws_caller_identity.current.account_id}:task-definition/${aws_ecs_task_definition.job.family}"
}

# Lets Scheduler start the task, and nothing else.
data "aws_iam_policy_document" "scheduler_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["scheduler.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_iam_role" "job_scheduler" {
  name               = "${var.project}-job-scheduler"
  assume_role_policy = data.aws_iam_policy_document.scheduler_assume.json
}

data "aws_iam_policy_document" "job_scheduler" {
  statement {
    sid     = "RunJob"
    actions = ["ecs:RunTask"]
    resources = [
      local.job_task_definition_family_arn,
      "${local.job_task_definition_family_arn}:*",
    ]
    condition {
      test     = "ArnEquals"
      variable = "ecs:cluster"
      values   = [aws_ecs_cluster.jobs.arn]
    }
  }

  statement {
    sid       = "PassJobRoles"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.job_execution.arn, aws_iam_role.job_task.arn]
    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy" "job_scheduler" {
  name   = "run-job"
  role   = aws_iam_role.job_scheduler.name
  policy = data.aws_iam_policy_document.job_scheduler.json
}

resource "aws_scheduler_schedule" "job" {
  name        = "${var.project}-job-daily"
  description = "Starts the job once a day."
  state       = var.schedule_enabled ? "ENABLED" : "DISABLED"

  # 5:00 AM Pacific, every day. The time zone handles daylight saving time.
  schedule_expression          = "cron(0 5 * * ? *)"
  schedule_expression_timezone = "America/Los_Angeles"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_ecs_cluster.jobs.arn
    role_arn = aws_iam_role.job_scheduler.arn

    ecs_parameters {
      # No revision number: ECS runs the newest ACTIVE revision, so a Release that pushes a new
      # image is picked up by the next run without changing the schedule.
      task_definition_arn = local.job_task_definition_family_arn
      launch_type         = "FARGATE"
      task_count          = 1

      network_configuration {
        subnets          = data.aws_subnets.default.ids
        security_groups  = [aws_security_group.job.id]
        assign_public_ip = true
      }
    }

    # If Scheduler can't start the task (for example a transient AWS error), retry briefly instead
    # of the default 24 hours, which could start the job at an odd time.
    retry_policy {
      maximum_retry_attempts       = 3
      maximum_event_age_in_seconds = 3600
    }
  }
}
