.DEFAULT_GOAL := help
# hooks mutates the tree (pre-commit stash + auto-fixes) while lint/test/docs
# read it — never interleave check's prerequisites under -j.
.NOTPARALLEL:

PYTHON     ?= python3
VENV_DIR   ?= .venv
VENV_BIN    = $(VENV_DIR)/bin
# Overridable so CI (system install, no venv) passes PYTEST=pytest.
PYTEST     ?= $(VENV_BIN)/pytest

# ---------------------------------------------------------------------------
# Development environment
# ---------------------------------------------------------------------------

.PHONY: setup
setup: ## Create virtual environment and install all dependencies
	@# Preflight: fail fast (with guidance) if $(PYTHON) is older than the
	@# requires-python floor declared in pyproject.toml (the single source of truth).
	@$(PYTHON) -c 'import re,sys,pathlib; spec=re.search(r"requires-python\s*=\s*\"([^\"]+)\"", pathlib.Path("pyproject.toml").read_text())[1]; need=tuple(map(int, re.search(r"(\d+)\.(\d+)", spec).groups())); sys.exit(0 if sys.version_info[:2] >= need else f"\n✗ kibana-py needs Python {spec}, but {sys.executable} is {sys.version.split()[0]}.\n  Re-run e.g.  make setup PYTHON=python3.11\n")'
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_BIN)/pip install --upgrade pip
	$(VENV_BIN)/pip install -e ".[dev,all]"
	$(VENV_BIN)/pre-commit install --install-hooks --hook-type pre-commit --hook-type pre-push
	@echo "\n✓ Dev environment ready. Activate with: source $(VENV_DIR)/bin/activate"
	@echo "✓ Pre-commit hooks installed (pre-commit + pre-push)."

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
	$(VENV_BIN)/pytest tests/unit/ --cov=kibana --cov-fail-under=90

.PHONY: test-integration
test-integration: stack-start ## Run integration tests (starts stack if needed)
	$(VENV_BIN)/pytest tests/integration/

.PHONY: test-integration-ci
test-integration-ci: ## Release-gate integration selection vs an already-provisioned stack (no stack-start; release.yml calls this; needs the [probe] extra for --timeout)
	$(PYTEST) tests/integration/ -m "not flaky" -o addopts="" -p no:randomly -p no:cacheprovider --timeout=180 --timeout-method=signal -q -ra

.PHONY: test-benchmark
test-benchmark: stack-start ## Run performance benchmarks
	$(VENV_BIN)/pytest tests/benchmark/

# --error-on-missing-interpreters makes nox FAIL (not silently skip) when any of
# the supported interpreters is absent, so matrix_green can't fail-open to a
# single-interpreter run on an incomplete host (#29). Install the missing
# interpreters (e.g. via pyenv) to run the full matrix.
.PHONY: test-python-matrix
test-python-matrix: ## Run unit tests across all supported Python versions via nox (required before release)
	@if command -v pyenv >/dev/null 2>&1; then \
		PYENV_VERSIONS="$$(pyenv versions --bare | awk '/^3\.(11|12|13|14)(\.|$$)/ {print $$1}' | paste -sd: -)"; \
		if [ -n "$$PYENV_VERSIONS" ]; then \
			PYENV_VERSION="$$PYENV_VERSIONS" \
			PATH="$(VENV_BIN):$$(pyenv root)/bin:$$(pyenv root)/shims:$$PATH" \
			$(VENV_BIN)/nox --error-on-missing-interpreters -s test; \
		else \
			PATH="$(VENV_BIN):$$PATH" $(VENV_BIN)/nox --error-on-missing-interpreters -s test; \
		fi; \
	else \
		PATH="$(VENV_BIN):$$PATH" $(VENV_BIN)/nox --error-on-missing-interpreters -s test; \
	fi

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

.PHONY: check
check: hooks lint audit sast test docs ## Local PR gate: hooks+lint+audit+sast+unit+docs (the vocabulary floor; matches GitHub Actions)
	@echo "\n✓ All checks passed. Note: run 'make test-python-matrix' to verify across all supported Python versions."

.PHONY: hooks
hooks: ## Run pre-commit-stage hooks on all files (plus the manual-stage pin check CI runs)
	$(VENV_BIN)/pre-commit run --all-files
	$(VENV_BIN)/pre-commit run check-pin-comments-match --hook-stage manual --all-files

.PHONY: lint
lint: ## Run mypy type checker
	$(VENV_BIN)/mypy kibana/

.PHONY: audit
audit: ## Audit dependencies for known vulnerabilities
	$(VENV_BIN)/pip-audit

.PHONY: sast
sast: ## Run SAST scan with bandit
	$(VENV_BIN)/bandit -r kibana/ -ll -q

.PHONY: fix
fix: ## Apply auto-fixes via pinned pre-commit hooks (isort, black, ruff-check --fix)
	$(VENV_BIN)/pre-commit run isort --all-files
	$(VENV_BIN)/pre-commit run black --all-files
	$(VENV_BIN)/pre-commit run ruff-check --all-files

# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------

.PHONY: dod
dod: ## Run the Definition-of-Done gate (GO/NO-GO over dod.config)
	scripts/checks/definition-of-done.sh

# ---------------------------------------------------------------------------
# Build & docs
# ---------------------------------------------------------------------------

.PHONY: build
build: ## Build wheel and sdist into dist/, then validate artifacts with twine
	$(VENV_BIN)/python -m build
	$(VENV_BIN)/python -m twine check dist/*

.PHONY: docs
docs: ## Build and link-check Sphinx documentation (matches CI)
	$(VENV_BIN)/sphinx-build -W --keep-going -b html docs/source docs/build/html
	$(VENV_BIN)/sphinx-build -b linkcheck docs/source docs/build/linkcheck
	$(VENV_BIN)/pre-commit run check-diagrams-rendered --hook-stage manual --all-files

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
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'
