output "lambda_function_name" {
  description = "Name of the deployed Lambda function"
  value       = aws_lambda_function.bot.function_name
}

output "lambda_function_arn" {
  description = "ARN of the deployed Lambda function"
  value       = aws_lambda_function.bot.arn
}

output "s3_state_bucket" {
  description = "S3 bucket that holds the seen-jobs state"
  value       = aws_s3_bucket.state.bucket
}

output "schedule_arns" {
  description = "ARNs of the three EventBridge Scheduler rules"
  value       = { for k, s in aws_scheduler_schedule.bot : k => s.arn }
}

output "ses_sender_verification" {
  description = "Check this email inbox to verify the SES sender address"
  value       = var.sender_email
}

output "ses_recipient_verification" {
  description = "Check this email inbox to verify the SES recipient address (sandbox only)"
  value       = var.recipient_email
}
