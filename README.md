# Meridian Assurance claims intake and servicing platform

Personal lines claims intake (FNOL), triage, reserving and settlement for Meridian Assurance,
plus the operations console that claims handlers work in.

The product specification is the source of truth for behaviour: [docs/PRD.md](docs/PRD.md).
The wire contract is described in [docs/api-contract.md](docs/api-contract.md) and the
architecture decisions are recorded in [docs/adr](docs/adr).

## Repository layout

| Path | Contents |
| --- | --- |
| `services/api` | Python 3.12 FastAPI service, SQLAlchemy 2 models, Alembic migrations, triage rules, outbox dispatcher |
| `apps/console` | React 18 + TypeScript + Vite operations console, typed against the published OpenAPI schema |
| `docs` | Product requirements, API contract, architecture decision records |
| `infra/terraform` | Cloud footprint for dev, staging and production |
| `infra/k8s` | Kustomize base and per environment overlays |
| `.github/workflows` | Continuous integration |

## Prerequisites

- Python 3.12
- Node.js 20.11 or newer
- Docker with the Compose plugin

## Run the stack

```bash
cp .env.example .env          # optional, only needed to move published ports
make up                       # builds and starts api, console, postgres, minio, mailpit
```

The API applies its migrations on start. Once `make up` reports the services as healthy:

- Console: <http://localhost:5173>
- API docs: <http://localhost:8000/docs>
- Object store console: <http://localhost:9001>
- Captured mail: <http://localhost:8025>

Load representative claims so the queue is not empty:

```bash
make install-api              # one off, creates services/api/.venv
CLAIMS_DATABASE_URL=postgresql+psycopg://claims:claims@localhost:5432/claims make seed
```

Stop everything and discard the volumes with `make down`.

The local stack runs the API with `CLAIMS_AUTH_DISABLED=true` so the console can be used without
an identity provider. Every other environment verifies OIDC bearer tokens; see
[docs/adr/0002-python-fastapi-postgres.md](docs/adr/0002-python-fastapi-postgres.md) and FR-080 in
the PRD.

## Develop

```bash
make install                  # API virtualenv plus console node_modules
make verify                   # lint, type check and every test suite bar the browser tests
```

Useful individual targets, all listed by `make help`:

| Target | Purpose |
| --- | --- |
| `make test-unit` | Rules engine, state machine, SLA and outbox tests, no database needed |
| `make test-api` | Adds the Postgres integration tests and the OpenAPI contract tests |
| `make test-console` | Vitest and React Testing Library component tests |
| `make e2e` | Playwright browser tests against a production build of the console |
| `make migrate` | Apply migrations to the configured database |
| `make migration-check` | Fail if the models and migrations have drifted apart |
| `make openapi` | Regenerate `services/api/openapi.json` and the console types |

### Database for the tests

The integration tests need a `claims_test` database. With the stack running:

```bash
docker compose exec postgres createdb -U claims claims_test
make test-api
```

Point the suite elsewhere with `CLAIMS_TEST_DATABASE_URL`.

### Changing the API surface

`services/api/openapi.json` is committed and the console types are generated from it. After
changing a route or a schema, run `make openapi` and commit both files, otherwise the OpenAPI drift
check in CI fails.

### Changing the data model

Create a migration alongside the model change:

```bash
cd services/api
../../services/api/.venv/bin/alembic revision --autogenerate -m "describe the change"
```

Review the generated file, then run `make migration-check`.

### Triage rules

Routing is data, not code: `services/api/src/claims_intake/rules/triage.yaml` holds a versioned,
first match wins rule set (ADR 0004). Bump `version` when you change it; the applied version is
stored on every triage decision so a past routing outcome can always be explained.

## Observability

- JSON logs on stdout, one object per line, each carrying the correlation id from
  `X-Correlation-Id` (generated when the caller does not supply one).
- Prometheus metrics on `GET /metrics` for the API, and port 9101 for the outbox dispatcher.
- `GET /healthz` is a liveness probe, `GET /readyz` checks the database and the object store.
- OpenTelemetry traces are exported when `CLAIMS_OTEL_EXPORTER_OTLP_ENDPOINT` is set.

## Deployment

Terraform in `infra/terraform` describes the network, managed Postgres, container service, object
storage and secret material for each environment. Kubernetes manifests live in `infra/k8s` as a
Kustomize base with `dev`, `staging` and `prod` overlays. No environment holds a secret value in
the repository: containers read them from the platform secret store.
