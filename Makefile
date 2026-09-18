SHELL := /bin/bash
API_DIR := services/api
CONSOLE_DIR := apps/console
VENV := $(API_DIR)/.venv
PY := $(VENV)/bin/python
COMPOSE := docker compose

export CLAIMS_TEST_DATABASE_URL ?= postgresql+psycopg://claims:claims@localhost:$(or $(POSTGRES_PORT),5432)/claims_test

.DEFAULT_GOAL := help

.PHONY: help
help: ## List the available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: install-api install-console ## Install API and console dependencies

.PHONY: install-api
install-api: ## Create the API virtualenv and install pinned dependencies
	python3.12 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r $(API_DIR)/requirements-dev.txt
	$(VENV)/bin/pip install --no-deps -e $(API_DIR)

.PHONY: install-console
install-console: ## Install console dependencies from the lockfile
	cd $(CONSOLE_DIR) && npm ci

.PHONY: up
up: ## Start the local stack (API, console, Postgres, object store, mail)
	$(COMPOSE) up --build -d
	$(COMPOSE) ps

.PHONY: down
down: ## Stop the local stack and remove volumes
	$(COMPOSE) down -v

.PHONY: logs
logs: ## Follow the API logs
	$(COMPOSE) logs -f api

.PHONY: migrate
migrate: ## Apply database migrations to the configured database
	cd $(API_DIR) && ../../$(VENV)/bin/alembic upgrade head

.PHONY: migration-check
migration-check: ## Fail when the models and migrations have drifted
	cd $(API_DIR) && ../../$(VENV)/bin/alembic upgrade head && ../../$(VENV)/bin/alembic check

.PHONY: seed
seed: ## Load representative claims into the database
	cd $(API_DIR) && ../../$(VENV)/bin/python -m claims_intake.seed

.PHONY: openapi
openapi: ## Regenerate openapi.json and the console API types
	cd $(API_DIR) && ../../$(VENV)/bin/python scripts/export_openapi.py
	cd $(CONSOLE_DIR) && npm run api:types

.PHONY: openapi-check
openapi-check: ## Fail when the committed OpenAPI schema or console types are stale
	cd $(API_DIR) && ../../$(VENV)/bin/python scripts/export_openapi.py
	cd $(CONSOLE_DIR) && npm run api:types
	git diff --exit-code -- $(API_DIR)/openapi.json $(CONSOLE_DIR)/src/api/schema.d.ts

.PHONY: lint
lint: ## Lint the API and the console
	cd $(API_DIR) && ../../$(VENV)/bin/ruff check .
	cd $(API_DIR) && ../../$(VENV)/bin/ruff format --check .
	cd $(CONSOLE_DIR) && npm run lint && npm run format:check

.PHONY: typecheck
typecheck: ## Type check the API and the console
	cd $(API_DIR) && ../../$(VENV)/bin/mypy
	cd $(CONSOLE_DIR) && npm run typecheck

.PHONY: test
test: test-api test-console ## Run every test suite except the browser tests

.PHONY: test-api
test-api: ## Run API unit, integration and contract tests
	cd $(API_DIR) && ../../$(VENV)/bin/python -m pytest tests

.PHONY: test-unit
test-unit: ## Run only the API tests that do not need a database
	cd $(API_DIR) && ../../$(VENV)/bin/python -m pytest tests/unit

.PHONY: test-console
test-console: ## Run console component tests
	cd $(CONSOLE_DIR) && npm run test

.PHONY: e2e
e2e: ## Run the Playwright browser tests
	cd $(CONSOLE_DIR) && npx playwright install --with-deps chromium && npm run e2e

.PHONY: build
build: ## Build the console bundle and both container images
	cd $(CONSOLE_DIR) && npm run build
	$(COMPOSE) build

.PHONY: verify
verify: lint typecheck test ## Everything CI runs, except the browser tests
