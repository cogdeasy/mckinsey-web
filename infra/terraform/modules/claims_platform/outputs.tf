output "api_endpoint" {
  description = "Public DNS name of the API load balancer"
  value       = module.service.load_balancer_dns_name
}

output "documents_bucket" {
  description = "Bucket holding claim evidence"
  value       = module.documents.bucket_name
}

output "database_endpoint" {
  description = "Endpoint of the managed Postgres instance"
  value       = module.database.endpoint
}

output "database_url_secret_arn" {
  description = "Secret holding the database connection string"
  value       = module.database.database_url_secret_arn
}
