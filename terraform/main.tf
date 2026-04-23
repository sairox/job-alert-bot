terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# ── Data ──────────────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}

# ── S3 — state persistence ────────────────────────────────────────────────────

resource "aws_s3_bucket" "state" {
  bucket        = var.s3_bucket_name
  force_destroy = false

  tags = { Project = "job-alert-bot" }
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── IAM — Lambda execution role ───────────────────────────────────────────────

resource "aws_iam_role" "lambda" {
  name = "job-alert-bot-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = { Project = "job-alert-bot" }
}

resource "aws_iam_role_policy_attachment" "basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "bot" {
  name = "job-alert-bot-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "S3ListBucket"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.state.arn
      },
      {
        Sid      = "S3State"
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.state.arn}/job-alert-bot/*"
      },
      {
        Sid      = "SESEmail"
        Effect   = "Allow"
        Action   = "ses:SendEmail"
        Resource = "*"
      }
    ]
  })
}

# ── Lambda function ───────────────────────────────────────────────────────────

resource "aws_lambda_function" "bot" {
  function_name = "job-alert-bot"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = var.ecr_image_uri
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout_sec
  architectures = ["x86_64"]

  environment {
    variables = {
      USE_PLAYWRIGHT  = "true"
      USE_SES         = "true"
      USE_S3          = "true"
      S3_BUCKET       = aws_s3_bucket.state.bucket
      S3_KEY          = "job-alert-bot/seen_jobs.json"
      SENDER_EMAIL    = var.sender_email
      # RECIPIENT_EMAIL is hardcoded in config.py; override here if needed
      REQUEST_TIMEOUT = "120"
      PLAYWRIGHT_BROWSERS_PATH  = "/ms-playwright"
    }
  }

  tags = { Project = "job-alert-bot" }
}

resource "aws_cloudwatch_log_group" "bot" {
  name              = "/aws/lambda/${aws_lambda_function.bot.function_name}"
  retention_in_days = 14
  tags              = { Project = "job-alert-bot" }
}

# ── EventBridge Scheduler — 7 AM, 12 PM, 6 PM Central ───────────────────────

resource "aws_iam_role" "scheduler" {
  name = "job-alert-bot-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_invoke" {
  name = "invoke-lambda"
  role = aws_iam_role.scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.bot.arn
    }]
  })
}

locals {
  schedules = {
    morning = "cron(0 7 * * ? *)"
    midday  = "cron(0 12 * * ? *)"
    evening = "cron(0 18 * * ? *)"
  }
}

resource "aws_scheduler_schedule" "bot" {
  for_each = local.schedules

  name                         = "job-alert-bot-${each.key}"
  group_name                   = "default"
  schedule_expression          = each.value
  schedule_expression_timezone = "America/Chicago"

  flexible_time_window { mode = "OFF" }

  target {
    arn      = aws_lambda_function.bot.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ source = "eventbridge-scheduler", run = each.key })

    retry_policy {
      maximum_retry_attempts       = 2
      maximum_event_age_in_seconds = 3600
    }
  }
}

# ── Lambda permission for EventBridge Scheduler ───────────────────────────────

resource "aws_lambda_permission" "scheduler" {
  for_each      = local.schedules
  statement_id  = "AllowScheduler-${each.key}"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.bot.function_name
  principal     = "scheduler.amazonaws.com"
  source_arn    = aws_scheduler_schedule.bot[each.key].arn
}

# ── SES email identity (manual verification required) ─────────────────────────

resource "aws_ses_email_identity" "sender" {
  email = var.sender_email
}

resource "aws_ses_email_identity" "recipient" {
  email = var.recipient_email
}
