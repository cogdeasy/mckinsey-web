variable "region" {
  description = "AWS region for this environment"
  type        = string
  default     = "eu-west-2"
}

variable "api_image" {
  description = "Container image released to this environment"
  type        = string
}

variable "certificate_arn" {
  description = "ACM certificate presented by the public load balancer"
  type        = string
}

variable "otlp_endpoint" {
  description = "OpenTelemetry collector endpoint for this environment"
  type        = string
}
