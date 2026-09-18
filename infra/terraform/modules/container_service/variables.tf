variable "name" {
  description = "Name prefix for the service resources"
  type        = string
}

variable "region" {
  description = "AWS region hosting the service"
  type        = string
}

variable "vpc_id" {
  description = "VPC hosting the service"
  type        = string
}

variable "public_subnet_ids" {
  description = "Subnets for the load balancer"
  type        = list(string)
}

variable "private_subnet_ids" {
  description = "Subnets for the tasks"
  type        = list(string)
}

variable "service_security_group_id" {
  description = "Security group attached to the tasks, also allowed into the database"
  type        = string
}

variable "image" {
  description = "Fully qualified container image for the API"
  type        = string
}

variable "container_port" {
  description = "Port the API listens on"
  type        = number
  default     = 8000
}

variable "task_cpu" {
  description = "Fargate CPU units"
  type        = number
  default     = 1024
}

variable "task_memory" {
  description = "Fargate memory in mebibytes"
  type        = number
  default     = 2048
}

variable "desired_count" {
  description = "Baseline number of tasks"
  type        = number
  default     = 2
}

variable "max_count" {
  description = "Upper bound for autoscaling"
  type        = number
  default     = 10
}

variable "environment" {
  description = "Plain environment variables for the container"
  type        = map(string)
  default     = {}
}

variable "secrets" {
  description = "Environment variables sourced from Secrets Manager, keyed by variable name"
  type        = map(string)
  default     = {}
}

variable "secret_arns" {
  description = "Secret ARNs the execution role may read"
  type        = list(string)
}

variable "documents_bucket_arn" {
  description = "ARN of the claim evidence bucket"
  type        = string
}

variable "kms_key_arn" {
  description = "Customer managed key used by the service"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate presented by the load balancer"
  type        = string
}

variable "ingress_cidr" {
  description = "CIDR allowed to reach the load balancer"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention"
  type        = number
  default     = 30
}

variable "deletion_protection" {
  description = "Protect the load balancer from deletion"
  type        = bool
  default     = true
}

variable "enable_execute_command" {
  description = "Allow operators to open a shell in a running task"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Tags applied to every resource"
  type        = map(string)
  default     = {}
}
