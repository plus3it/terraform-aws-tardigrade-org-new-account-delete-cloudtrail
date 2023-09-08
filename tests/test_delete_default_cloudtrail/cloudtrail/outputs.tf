output "s3_bucket_arn" {
  value = aws_s3_bucket.this.arn
}

output "cloudtrail_arn" {
  value = aws_cloudtrail.this.arn
}
