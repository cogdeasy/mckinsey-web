variable "bucket_name" {
  description = "Globally unique bucket name for claim evidence"
  type        = string
}

variable "kms_key_arn" {
  description = "Customer managed key used for object encryption"
  type        = string
}

variable "allowed_origins" {
  description = "Origins permitted to use presigned upload and download URLs"
  type        = list(string)
}

variable "retention_days" {
  description = "How long claim evidence is retained"
  type        = number
  default     = 2555
}

variable "tags" {
  description = "Tags applied to every resource"
  type        = map(string)
  default     = {}
}
