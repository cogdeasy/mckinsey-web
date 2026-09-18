terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }

  # Configured at init time, for example:
  #   terraform init -backend-config=backend.hcl
  backend "s3" {}
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Application = "claims-intake-service"
      Environment = "dev"
    }
  }
}

module "platform" {
  source = "../../modules/claims_platform"

  environment             = "dev"
  region                  = var.region
  vpc_cidr                = "10.60.0.0/16"
  availability_zone_count = 2
  production_grade        = false

  api_image               = var.api_image
  api_desired_count       = 1
  api_max_count           = 4
  api_task_cpu            = 512
  api_task_memory         = 1024
  database_instance_class = "db.t4g.medium"

  certificate_arn = var.certificate_arn
  ingress_cidr    = "10.0.0.0/8"
  console_origin  = "https://claims-console.dev.meridian-assurance.example"
  oidc_issuer     = "https://id.dev.meridian-assurance.example/"
  otlp_endpoint   = var.otlp_endpoint
  log_level       = "DEBUG"
}
