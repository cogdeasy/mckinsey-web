# Cloud footprint

Each environment is a separate state file and a separate AWS account. The composition lives in
`modules/claims_platform`, which wires together the reusable modules:

| Module | Purpose |
| --- | --- |
| `modules/network` | VPC, public and private subnets across availability zones, NAT, S3 gateway endpoint |
| `modules/database` | Managed Postgres 16, encrypted storage, backups, connection string in Secrets Manager |
| `modules/object_storage` | Private, versioned, KMS encrypted bucket for claim evidence |
| `modules/container_service` | ECS Fargate service for the API behind an HTTPS load balancer, with autoscaling |

## Usage

```bash
cd environments/dev
cp backend.hcl.example backend.hcl        # fill in the account specific values
terraform init -backend-config=backend.hcl
terraform plan -var "api_image=<registry>/claims-intake-api:<tag>" \
                -var "certificate_arn=<acm arn>" \
                -var "otlp_endpoint=https://otlp.dev.meridian-assurance.example"
```

## Secrets

No secret value is stored in this repository or in Terraform variables. The database password is
generated at apply time and written to Secrets Manager; the OIDC signing material is created as an
empty secret and populated by the identity platform. Tasks receive both as container secrets, so
they never appear in a task definition in plain text.

## Environment differences

| | dev | staging | prod |
| --- | --- | --- | --- |
| Availability zones | 2 | 2 | 3 |
| NAT gateways | 1 | 1 | one per zone |
| Database | `db.t4g.medium`, single AZ | `db.m7g.large`, single AZ | `db.m7g.xlarge`, multi AZ |
| Backup retention | 7 days | 7 days | 30 days |
| API tasks | 1 to 4 | 2 to 6 | 4 to 16 |
| Deletion protection | off | off | on |
| Task shell access | allowed | allowed | denied |
