output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.this.name
}

output "service_name" {
  description = "Name of the API service"
  value       = aws_ecs_service.api.name
}

output "load_balancer_dns_name" {
  description = "DNS name of the public load balancer"
  value       = aws_lb.this.dns_name
}
