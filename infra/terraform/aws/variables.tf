variable "region" {
  type    = string
  default = "eu-west-3" # Paris
}

variable "bucket_name" {
  type        = string
  description = "Globally unique S3 bucket name, e.g. ragops-landing-<suffix>"
}

variable "retention_days" {
  type    = number
  default = 90
}

output "bucket" {
  value = aws_s3_bucket.landing.bucket
}

output "writer_policy_arn" {
  value = aws_iam_policy.writer.arn
}
