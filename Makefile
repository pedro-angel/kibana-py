.DEFAULT_GOAL := help

PYTHON     ?= python3
VENV_DIR   ?= .venv
VENV_BIN    = $(VENV_DIR)/bin

# ---------------------------------------------------------------------------
# Development environment
# ---------------------------------------------------------------------------

.PHONY: setup
setup: ## Create virtual environment and install all dependencies
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -e ".[dev,all]"
	@echo "\n✓ Dev environment ready. Activate with: source $(VENV_DIR)/bin/activate"

# ---------------------------------------------------------------------------
# Local Elastic Stack
# ---------------------------------------------------------------------------

.PHONY: stack-start
stack-start: ## Start local Elastic Stack (Elasticsearch, Kibana, APM server)
	./local-stack.sh -o start

.PHONY: stack-stop
stack-stop: ## Stop local Elastic Stack
	./local-stack.sh -o stop

.PHONY: stack-status
stack-status: ## Show local Elastic Stack container status
	./local-stack.sh -o status

.PHONY: stack-destroy
stack-destroy: ## Destroy local Elastic Stack and delete all data (fresh start)
	./local-stack.sh -o destroy

# ---------------------------------------------------------------------------
# Testing
# ---------------------------------------------------------------------------

.PHONY: test
test: ## Run unit tests with coverage
	$(VENV_BIN)/pytest tests/unit/ --cov=kibana --cov-fail-under=75

.PHONY: test-integration
test-integration: stack-start ## Run integration tests (starts stack if needed)
	$(VENV_BIN)/pytest tests/integration/

.PHONY: benchmark
benchmark: stack-start ## Run performance benchmarks
	$(VENV_BIN)/pytest tests/benchmark/

.PHONY: test-all
test-all: ## Run tests across Python versions via nox
	PATH=$(VENV_BIN):$$PATH $(VENV_BIN)/nox -s test

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

.PHONY: check
check: lint test ## Run all CI checks locally (lint + type check + unit tests)

.PHONY: lint
lint: ## Run ruff linter and mypy type checker
	$(VENV_BIN)/ruff check kibana/ tests/
	$(VENV_BIN)/mypy kibana/

.PHONY: format
format: ## Auto-format code with isort and black
	$(VENV_BIN)/isort kibana/ tests/ examples/
	$(VENV_BIN)/black kibana/ tests/ examples/

.PHONY: format-check
format-check: ## Check code formatting without making changes
	$(VENV_BIN)/isort --check-only kibana/ tests/ examples/
	$(VENV_BIN)/black --check kibana/ tests/ examples/

# ---------------------------------------------------------------------------
# Build & docs
# ---------------------------------------------------------------------------

.PHONY: build
build: ## Build wheel and sdist into dist/
	$(VENV_BIN)/python -m build

.PHONY: docs
docs: ## Build Sphinx documentation
	$(VENV_BIN)/sphinx-build docs/source docs/build

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

.PHONY: clean
clean: ## Remove build artifacts, caches, and coverage data
	rm -rf build/ dist/ *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage coverage.xml htmlcov
	rm -rf docs/build/ .nox/

.PHONY: clean-all
clean-all: clean ## Remove everything including the virtual environment
	rm -rf $(VENV_DIR)

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

.PHONY: help
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
