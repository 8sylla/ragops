# Landing zone for the raw archives on AWS S3: versioned, encrypted, private,
# with a writer policy limited to this bucket.

terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_s3_bucket" "landing" {
  bucket = var.bucket_name
  tags = {
    project = "ragops"
    layer   = "landing"
  }
}

resource "aws_s3_bucket_versioning" "landing" {
  bucket = aws_s3_bucket.landing.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "landing" {
  bucket = aws_s3_bucket.landing.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "landing" {
  bucket                  = aws_s3_bucket.landing.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "landing" {
  bucket = aws_s3_bucket.landing.id
  rule {
    id     = "expire-old-archives"
    status = "Enabled"
    filter {
      prefix = "vosdroits/"
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    expiration {
      days = var.retention_days
    }
  }
}

data "aws_iam_policy_document" "writer" {
  statement {
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.landing.arn}/vosdroits/*"]
  }
  statement {
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.landing.arn]
  }
}

resource "aws_iam_policy" "writer" {
  name   = "${var.bucket_name}-writer"
  policy = data.aws_iam_policy_document.writer.json
}
