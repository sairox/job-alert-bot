variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "ecr_image_uri" {
  description = "Full ECR image URI for the Lambda container (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/job-alert-bot:latest)"
  type        = string
}

variable "sender_email" {
  description = "Verified SES sender email address"
  type        = string
}

variable "recipient_email" {
  description = "Email address to receive job alerts"
  type        = string
  default     = "saiviks81@gmail.com"
}

variable "s3_bucket_name" {
  description = "S3 bucket name for persisting seen-job state"
  type        = string
  default     = "job-alert-bot-state"
}

variable "keywords" {
  description = "Comma-separated keywords both must appear in a job title/department"
  type        = string
  default     = "Software,Engineer"
}

variable "lambda_memory_mb" {
  description = "Lambda memory allocation (MB). Playwright needs >= 1024 MB."
  type        = number
  default     = 1024
}

variable "lambda_timeout_sec" {
  description = "Lambda timeout in seconds"
  type        = number
  default     = 300
}
