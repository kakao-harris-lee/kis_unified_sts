# KIS Unified STS — developer convenience targets.
# Run `make` (or `make help`) to list everything. Two ways to work from a fresh
# clone: in Docker (no host setup beyond Docker) or on the host (Python 3.11).

.DEFAULT_GOAL := help
SHELL := /usr/bin/env bash
COMPOSE ?= docker compose

# Two-pass pytest mirroring .github/workflows/test.yml (parallel non-serial,
# then serial), with the performance suite excluded (it has its own CI job).
PYTEST_FLAGS := --ignore=tests/performance --timeout=180 --timeout-method=thread -q

.PHONY: help setup env test test-unit test-docker lint fmt typecheck up down ui clean

help: ## List available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

setup: env ## Install Python deps (editable + dev extras) into the active env
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]" prometheus-client

env: ## Create .env from .env.example if it does not exist
	@test -f .env || { cp .env.example .env && echo "created .env from .env.example"; }

test: ## Full suite on the host (needs Python 3.11 + a Redis at localhost:6379)
	pytest tests/ $(PYTEST_FLAGS) -n auto -m "not serial"
	pytest tests/ $(PYTEST_FLAGS) -m serial

test-unit: ## Fast host subset (unit tests only; fakeredis, no external Redis)
	pytest tests/unit $(PYTEST_FLAGS) -n auto

test-docker: ## Full suite in Docker — zero host setup beyond Docker (CI parity)
	$(COMPOSE) --profile test run --build --rm tests

lint: ## ruff + black --check
	ruff check .
	black --check .

fmt: ## Auto-format (black + ruff --fix)
	black .
	ruff check . --fix

typecheck: ## mypy on shared/
	mypy shared/ --ignore-missing-imports --no-error-summary

up: ## Start the default Docker stack (detached)
	$(COMPOSE) up -d

down: ## Stop the Docker stack incl. the test profile
	$(COMPOSE) --profile test down --remove-orphans

ui: ## Run the frontend dev server (strategy-builder-ui)
	cd strategy-builder-ui && npm install && npm run dev

clean: ## Remove caches and build artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov
