variable "environment" {
  description = "Environment name, used as a suffix on every resource"
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be one of dev, staging or prod."
  }
}

variable "region" {
  description = "AWS region for the environment"
  type        = string
}

variable "vpc_cidr" {
  description = "IPv4 CIDR block for the environment VPC"
  type        = string
}

variable "availability_zone_count" {
  description = "Number of availability zones in use"
  type        = number
  default     = 2
}

variable "production_grade" {
  description = "Enable multi az, deletion protection and longer retention"
  type        = bool
  default     = false
}

variable "api_image" {
  description = "Container image for the claims intake API"
  type        = string
}

variable "api_desired_count" {
  description = "Baseline task count"
  type        = number
  default     = 2
}

variable "api_max_count" {
  description = "Maximum task count"
  type        = number
  default     = 8
}

variable "api_task_cpu" {
  description = "Fargate CPU units per task"
  type        = number
  default     = 1024
}

variable "api_task_memory" {
  description = "Fargate memory per task in mebibytes"
  type        = number
  default     = 2048
}

variable "database_instance_class" {
  description = "Instance class for managed Postgres"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate for the public listener"
  type        = string
}

variable "ingress_cidr" {
  description = "CIDR allowed to reach the load balancer"
  type        = string
}

variable "console_origin" {
  description = "Origin of the operations console, used for presigned upload CORS"
  type        = string
}

variable "oidc_issuer" {
  description = "Issuer that mints claims handler tokens"
  type        = string
}

variable "otlp_endpoint" {
  description = "OpenTelemetry collector endpoint"
  type        = string
}

variable "log_level" {
  description = "Log level for the API"
  type        = string
  default     = "INFO"
}

variable "tags" {
  description = "Additional tags applied to every resource"
  type        = map(string)
  default     = {}
}
