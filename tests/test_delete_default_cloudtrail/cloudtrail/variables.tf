variable "cloudtrail_name" {
  description = "Name of the test cloudtrail to create"
  type        = string
}

variable "cloudtrail_s3_name" {
  description = "Name of the s3 bucket for the test cloudtrail"
  type        = string
}

variable "tags" {
  description = "Tags for resource"
  type        = map(string)
  default     = {}
}
