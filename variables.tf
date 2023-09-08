variable "project_name" {
  description = "Project name to prefix resources with"
  type        = string
}

variable "assume_role_name" {
  description = "Name of the IAM role that the lambda will assume in the target account"
  type        = string
  default     = "OrganizationAccountAccessRole"
}

variable "cloudtrail_name_prefix" {
  description = "Name Prefix of the cloudtrail name to delete"
  type        = string
  default     = "cloudtrail-"
}

variable "error_not_found" {
  description = "Error if the cloudtrail name/pattern is not found"
  type        = bool
  default     = true
}

variable "event_bus_name" {
  description = "Event bus name to create event rules in"
  type        = string
  default     = "default"
}

variable "event_types" {
  description = "Event types that will trigger this lambda"
  type        = set(string)
  default = [
    "CreateAccountResult",
    "InviteAccountToOrganization",
  ]

  validation {
    condition     = alltrue([for event in var.event_types : contains(["CreateAccountResult", "InviteAccountToOrganization"], event)])
    error_message = "Supported event_types include only: CreateAccountResult, InviteAccountToOrganization"
  }
}

variable "dry_run" {
  description = "Boolean toggle to control the dry-run mode of the lambda function"
  type        = bool
  default     = true
}

variable "lambda" {
  description = "Object of optional attributes passed on to the lambda module"
  type = object({
    artifacts_dir            = optional(string, "builds")
    build_in_docker          = optional(bool, false)
    create_package           = optional(bool, true)
    ephemeral_storage_size   = optional(number)
    ignore_source_code_hash  = optional(bool, true)
    local_existing_package   = optional(string)
    memory_size              = optional(number, 128)
    recreate_missing_package = optional(bool, false)
    runtime                  = optional(string, "python3.8")
    s3_bucket                = optional(string)
    s3_existing_package      = optional(map(string))
    s3_prefix                = optional(string)
    store_on_s3              = optional(bool, false)
    timeout                  = optional(number, 300)
  })
  default = {}
}

variable "log_level" {
  description = "Log level for lambda"
  type        = string
  default     = "INFO"
  validation {
    condition     = contains(["CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"], var.log_level)
    error_message = "Valid values for log level are (CRITICAL, ERROR, WARNING, INFO, DEBUG)."
  }
}

variable "tags" {
  description = "Tags for resource"
  type        = map(string)
  default     = {}
}
