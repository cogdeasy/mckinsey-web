output "vpc_id" {
  description = "Identifier of the VPC"
  value       = aws_vpc.this.id
}

output "public_subnet_ids" {
  description = "Public subnet identifiers, used by the load balancer"
  value       = [for subnet in aws_subnet.public : subnet.id]
}

output "private_subnet_ids" {
  description = "Private subnet identifiers, used by tasks and the database"
  value       = [for subnet in aws_subnet.private : subnet.id]
}

output "cidr_block" {
  description = "CIDR block of the VPC"
  value       = aws_vpc.this.cidr_block
}
