# S3 — 증빙 사진 + 정적 파일
variable "env" {}

resource "aws_s3_bucket" "photos" {
  bucket        = "sepang-photos-${var.env}"
  force_destroy = var.env != "production"
}

resource "aws_s3_bucket_versioning" "photos" {
  bucket = aws_s3_bucket.photos.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  rule { apply_server_side_encryption_by_default { sse_algorithm = "AES256" } }
}

resource "aws_s3_bucket_public_access_block" "photos" {
  bucket                  = aws_s3_bucket.photos.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  rule {
    id     = "expire-old-photos"
    status = "Enabled"
    filter { prefix = "photos/" }
    expiration { days = 365 }   # 1년 후 삭제
    noncurrent_version_expiration { noncurrent_days = 30 }
  }
}

# CORS (점주 앱에서 직접 업로드)
resource "aws_s3_bucket_cors_configuration" "photos" {
  bucket = aws_s3_bucket.photos.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "PUT", "POST"]
    allowed_origins = ["https://partner.sepang.kr", "https://sepang.kr"]
    max_age_seconds = 3600
  }
}

output "bucket_name" { value = aws_s3_bucket.photos.id }
output "bucket_arn"  { value = aws_s3_bucket.photos.arn }
