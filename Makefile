.PHONY: help setup hooks up down db-reset test lint fmt scan check

help:
	@grep -E '^[a-z-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

setup: ## Install dependencies and git hooks
	uv sync --extra dev
	$(MAKE) hooks

hooks: ## Point git at the version-controlled hooks
	git config core.hooksPath .githooks
	@echo "hooks installed (pre-commit secret scan active)"

up: ## Start Postgres and MinIO
	docker compose up -d postgres minio

down: ## Stop containers
	docker compose down

db-reset: ## Drop and recreate the schema (destroys all data)
	uv run python scripts/reset_db.py

corpus: ## Ingest the bundled regulatory corpus
	uv run python scripts/ingest_corpus.py

eval-retrieval: ## Benchmark the retrieval spine against the labelled set
	uv run python -m nyaya.eval.retrieval_eval

eval-compliance: ## Measure the citation validator against the labelled set
	uv run python -m nyaya.eval.compliance_eval

test: ## Run the test suite
	uv run pytest -q

lint: ## Lint
	uv run ruff check nyaya/ tests/ scripts/

fmt: ## Format
	uv run ruff format nyaya/ tests/ scripts/
	uv run ruff check --fix nyaya/ tests/ scripts/

scan: ## Scan staged content for credentials
	uv run python scripts/check_secrets.py

check: lint test scan ## Everything CI would run
