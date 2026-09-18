variable "name" {
  description = "Name prefix for the database resources"
  type        = string
}

variable "vpc_id" {
  description = "VPC hosting the database"
  type        = string
}

variable "subnet_ids" {
  description = "Private subnets for the database subnet group"
  type        = list(string)
}

variable "client_security_group_id" {
  description = "Security group allowed to reach Postgres"
  type        = string
}

variable "kms_key_arn" {
  description = "Customer managed key used for storage and secret encryption"
  type        = string
}

variable "database_name" {
  description = "Initial database name"
  type        = string
  default     = "claims"
}

variable "master_username" {
  description = "Master user created with the instance"
  type        = string
  default     = "claims_app"
}

variable "engine_version" {
  description = "Postgres engine version"
  type        = string
  default     = "16.4"
}

variable "instance_class" {
  description = "Instance class for the database"
  type        = string
}

variable "allocated_storage" {
  description = "Initial storage in gibibytes"
  type        = number
  default     = 50
}

variable "max_allocated_storage" {
  description = "Upper bound for storage autoscaling in gibibytes"
  type        = number
  default     = 500
}

variable "multi_az" {
  description = "Run a standby in a second availability zone"
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "Automated backup retention"
  type        = number
  default     = 14
}

variable "deletion_protection" {
  description = "Refuse to destroy the instance and take a final snapshot"
  type        = bool
  default     = true
}

variable "secret_recovery_window_days" {
  description = "Days a deleted secret can be restored"
  type        = number
  default     = 7
}

variable "tags" {
  description = "Tags applied to every resource"
  type        = map(string)
  default     = {}
}
