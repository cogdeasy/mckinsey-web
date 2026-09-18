locals {
  name = "claims-${var.environment}"

  tags = merge(
    {
      Application = "claims-intake-service"
      Environment = var.environment
      Owner       = "claims-platform"
      ManagedBy   = "terraform"
    },
    var.tags,
  )
}

resource "aws_kms_key" "platform" {
  description             = "Encryption key for claims ${var.environment}"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = local.tags
}

resource "aws_kms_alias" "platform" {
  name          = "alias/${local.name}"
  target_key_id = aws_kms_key.platform.key_id
}

resource "aws_security_group" "tasks" {
  name        = "${local.name}-tasks"
  description = "Claims intake tasks"
  vpc_id      = module.network.vpc_id
  tags        = local.tags
}

resource "aws_vpc_security_group_egress_rule" "tasks_all" {
  security_group_id = aws_security_group.tasks.id
  description       = "Outbound to the database, object storage and identity provider"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

module "network" {
  source = "../network"

  name                    = local.name
  region                  = var.region
  cidr_block              = var.vpc_cidr
  availability_zone_count = var.availability_zone_count
  single_nat_gateway      = !var.production_grade
  tags                    = local.tags
}

module "documents" {
  source = "../object_storage"

  bucket_name     = "${local.name}-claim-documents"
  kms_key_arn     = aws_kms_key.platform.arn
  allowed_origins = [var.console_origin]
  tags            = local.tags
}

resource "aws_secretsmanager_secret" "jwt_signing" {
  name                    = "${local.name}/oidc-signing-key"
  description             = "Public signing material used to verify claims handler tokens"
  kms_key_id              = aws_kms_key.platform.arn
  recovery_window_in_days = var.production_grade ? 30 : 7
  tags                    = local.tags
}

module "database" {
  source = "../database"

  name                        = local.name
  vpc_id                      = module.network.vpc_id
  subnet_ids                  = module.network.private_subnet_ids
  client_security_group_id    = aws_security_group.tasks.id
  kms_key_arn                 = aws_kms_key.platform.arn
  instance_class              = var.database_instance_class
  multi_az                    = var.production_grade
  backup_retention_days       = var.production_grade ? 30 : 7
  deletion_protection         = var.production_grade
  secret_recovery_window_days = var.production_grade ? 30 : 7
  tags                        = local.tags
}

module "service" {
  source = "../container_service"

  name               = local.name
  region             = var.region
  vpc_id             = module.network.vpc_id
  public_subnet_ids  = module.network.public_subnet_ids
  private_subnet_ids = module.network.private_subnet_ids

  service_security_group_id = aws_security_group.tasks.id

  image                  = var.api_image
  desired_count          = var.api_desired_count
  max_count              = var.api_max_count
  task_cpu               = var.api_task_cpu
  task_memory            = var.api_task_memory
  certificate_arn        = var.certificate_arn
  ingress_cidr           = var.ingress_cidr
  documents_bucket_arn   = module.documents.bucket_arn
  kms_key_arn            = aws_kms_key.platform.arn
  deletion_protection    = var.production_grade
  enable_execute_command = !var.production_grade
  log_retention_days     = var.production_grade ? 90 : 30

  environment = {
    CLAIMS_ENVIRONMENT                 = var.environment
    CLAIMS_DOCUMENTS_BUCKET            = module.documents.bucket_name
    CLAIMS_S3_REGION                   = var.region
    CLAIMS_JWT_ISSUER                  = var.oidc_issuer
    CLAIMS_JWT_AUDIENCE                = "claims-intake-service"
    CLAIMS_JWT_ALGORITHM               = "RS256"
    CLAIMS_LOG_LEVEL                   = var.log_level
    CLAIMS_OTEL_EXPORTER_OTLP_ENDPOINT = var.otlp_endpoint
  }

  secrets = {
    CLAIMS_DATABASE_URL = module.database.database_url_secret_arn
    CLAIMS_JWT_SECRET   = aws_secretsmanager_secret.jwt_signing.arn
  }

  secret_arns = [
    module.database.database_url_secret_arn,
    aws_secretsmanager_secret.jwt_signing.arn,
  ]

  tags = local.tags
}
