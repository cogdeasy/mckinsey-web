output "api_endpoint" {
  description = "Public DNS name of the API load balancer"
  value       = module.platform.api_endpoint
}

output "documents_bucket" {
  description = "Bucket holding claim evidence"
  value       = module.platform.documents_bucket
}

output "database_url_secret_arn" {
  description = "Secret holding the database connection string"
  value       = module.platform.database_url_secret_arn
}
