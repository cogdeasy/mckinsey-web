output "endpoint" {
  description = "Connection endpoint of the database"
  value       = aws_db_instance.this.address
}

output "security_group_id" {
  description = "Security group attached to the database"
  value       = aws_security_group.database.id
}

output "database_url_secret_arn" {
  description = "Secrets Manager ARN holding the SQLAlchemy connection string"
  value       = aws_secretsmanager_secret.database_url.arn
}
