# Dependency Unification — Design

**Date:** 2026-07-08
**Status:** Approved design, pending spec review
**Scope:** Everything (Python deps + docs + linters/tooling + automation)
**Approach:** pyproject.toml as single source of truth (Approach 1)
**Delivery:** one focused PR, logically-separated commits

## Context

Merging the Dependabot backlog surfaced that the same dependencies are declared in
multiple places by copy-paste, and different consumers install from different copies. A
map of every declaration and consumer (workflow: `dependency-declaration-map`) found:

- **Sphinx toolchain declared three times** with now-drifting floors: `docs/requirements.txt`
  (bumped: copybutton≥0.5.2, design≥0.7.0, autobuild≥2025.8.25) vs pyproject `[docs]` extra
  vs pyproject `[dev]` extra (both still ≥0.5.0 / ≥2024). The **`[docs]` extra is an orphan**
  — nothing installs `.[docs]`. CI and `make docs` build from `[dev]`; only Read the Docs
  installs `requirements.txt`. So CI can pass while RTD builds a different Sphinx and fails.
- **`all` re-lists** async+orjson+observability verbatim; **`dev` re-lists** all six docs
  deps verbatim — any bump must be edited twice or the copies drift.
- **Formatter/linter versions live in two places**: the executed pins in
  `.pre-commit-config.yaml` (black 26.5.1, isort 8.0.1, ruff 0.15.20) vs floors in `dev`
  (black≥24, isort≥5, ruff≥0.1). `test.yml` even runs a *standalone* `ruff check .` from the
  `dev` floor — a different ruff than the pre-commit hook. Dependabot does not watch pre-commit.
- **Ad-hoc unpinned tools in CI**, invisible to Dependabot: `interrogate` (docs.yml),
  `cyclonedx-bom` (release.yml, declared nowhere), plus `build`/`twine`/`pre-commit`
  reinstalled standalone instead of from the extra that already declares them.
- **GitHub Actions versions are inconsistent** across workflows (main mixes
  `checkout@v4` and `@v6`, `upload-artifact@v4` and `@v7`), which is why Dependabot Action
  PRs #2–#6 now conflict.

**Goal:** every dependency and tool version declared exactly once; CI and Read the Docs
build from identical sources; Dependabot (and a pre-commit path) can see everything.

**Non-goals:** no lockfile / `uv` / `pip-tools` (deferred, YAGNI); no major-version bumps of
sphinx/furo (that decision is separate — see "Open PRs"). Build backend is **hatchling**,
which supports the self-referential extras this design relies on.

## Design

### 1. `pyproject.toml` — declare once, compose by reference

Runtime deps and the feature extras (`async`, `orjson`, `observability`) are unchanged —
each already declares its deps once. The aggregates and tooling extras change:

```toml
[project.optional-dependencies]
async = ["aiohttp>=3,<4"]
orjson = ["orjson>=3"]
observability = [
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-exporter-otlp-proto-grpc>=1.20.0",
    "opentelemetry-exporter-otlp-proto-http>=1.20.0",
    "opentelemetry-instrumentation>=0.40b0",
]

# The ONE Sphinx toolchain declaration (reconciled to the current, newest floors).
docs = [
    "sphinx>=7.0.0",
    "furo>=2024.1.0",
    "myst-parser>=2.0.0",
    "sphinx-copybutton>=0.5.2",
    "sphinx-design>=0.7.0",
    "sphinx-autobuild>=2025.8.25",
]

# The ONE release/build tooling declaration (was ad-hoc in release.yml).
build = ["build", "twine>=6.2.0", "cyclonedx-bom"]

# Feature aggregate (NOT install-everything) — self-reference, no verbatim copy.
all = ["kibana-py[async,orjson,observability]"]

# Directly-invoked tools only, plus references to docs + build toolchains.
dev = [
    "pytest>=7.0", "pytest-cov", "pytest-mock", "pytest-asyncio",
    "mypy>=1.0", "pyright", "types-python-dateutil",
    "pip-audit>=2.0", "bandit>=1.7",
    "interrogate",
    "nox", "pre-commit>=3.0", "psutil>=5.0",
    "kibana-py[docs,build]",
]
```

Key changes: `black`/`isort`/`ruff` **removed** from `dev` (pre-commit owns them, §3);
`interrogate` **added**; `build`/`twine` **moved** to the new `[build]` extra and pulled back
into `dev` by reference; docs deps **referenced** (`kibana-py[docs]`) instead of re-listed.

Consequence: `make setup` / nox (`.[dev,all]`) still install the full toolchain because `dev`
now references `docs` + `build`. No Makefile change needed.

### 2. Retire `docs/requirements.txt`

- **Delete** `docs/requirements.txt`.
- `.readthedocs.yaml` → single install source:
  ```yaml
  python:
    install:
      - method: pip
        path: .
        extra_requirements:
          - docs
  ```
  (Drops the `requirements.txt` line and the redundant `[dev]` install; the `post_install:
  pip install -e .` job becomes unnecessary and is removed.) RTD now builds from `.[docs]` —
  the same source as CI and local.
- **Update `docs.yml`**: its build-docs job references the deleted file as a pip cache key
  (`cache-dependency-path: docs/requirements.txt`) — repoint it to `pyproject.toml`, otherwise
  the workflow breaks on the missing path.

### 3. Linters single-sourced in pre-commit

- Remove `black`, `isort`, `ruff` from the `dev` extra. `.pre-commit-config.yaml` is their
  sole version *and* execution source.
- In `test.yml`, delete the standalone **`ruff check .`** step — the job already runs
  `pre-commit run --all-files`, which includes ruff/black/isort at the pinned revs.
- `mypy kibana/` stays (no pre-commit hook; sourced from `dev`).

### 4. CI consumers install from declared extras — lean where it helps

| Consumer | Before | After |
|---|---|---|
| `test.yml` unit job | `.[dev,async,orjson,observability]` | **`.[dev,all]`** (one spelling, matches Makefile/nox); drop `ruff check .` |
| `release.yml` build | `pip install build twine cyclonedx-bom` | **`pip install .[build]`** |
| `docs.yml` quality-checks | `pip install -e .` + `pip install interrogate` | **`pip install -e .[dev]`** (interrogate from the extra) |
| `docs.yml` build-docs | `make setup` | unchanged (sphinx now via `dev→docs` reference) |
| `checks.yml` pre-commit | `pip install pre-commit` | **unchanged** (kept lean — runner version isn't a correctness risk) |

All tool *versions* are now declared in pyproject; only the tiny pre-commit-runner install
stays bare, by choice.

### 5. Dependabot & GitHub Actions automation

- **Dependabot** (`.github/dependabot.yml`): remove the now-dead `pip` `/docs` entry; add
  `groups` to the `pip` `/` and `github-actions` entries so related updates arrive as one PR
  instead of ten.
- **Normalize GitHub Actions versions**: pin each action to a single target version across all
  four workflows — the newest version already present in the repo for that action (e.g.
  `checkout@v6`, `setup-python@v6`, `upload-artifact@v7`), or the latest stable release when no
  newer pin exists (`download-artifact`, `action-gh-release`). Keep the existing commit-SHA +
  `# vX.Y.Z` pinning style. This makes the github-actions surface consistent and lets grouped
  Dependabot updates stay clean.
- **Add `.github/workflows/pre-commit-autoupdate.yml`**: a scheduled weekly job that runs
  `pre-commit autoupdate` and opens a PR bumping the hook revs — covers the one surface
  Dependabot cannot watch. (Uses the standard `peter-evans/create-pull-request` action, pinned.)

### 6. Open Dependabot PRs — disposition

- **#7** (sphinx-design) — already merged; its floor is reflected in the new `[docs]`.
- **#8 furo, #9 sphinx (majors)** — target the retired `docs/requirements.txt`; **close them**.
  Major bumps are out of scope here; revisit as a `[docs]` change with a local docs build.
- **#2–#6 (Actions)** — resolved by the Actions normalization in §5; **close them** once the
  workflows pin consistent current versions.

## Verification

1. `pip install -e .[dev,all]` resolves (confirms hatchling self-references work).
2. `make setup && make check` passes (pre-commit + mypy + audit + sast + unit tests).
3. `make docs` builds HTML + linkcheck (sphinx sourced via `dev→docs`).
4. RTD-equivalent: fresh venv, `pip install .[docs]`, `sphinx-build -W docs/source out` passes.
5. `pip install .[build] && python -m build && twine check dist/*` succeeds.
6. `grep -rn "requirements.txt" .github .readthedocs.yaml` returns nothing (fully retired).
7. PR CI green (all four workflows), then a real `make test-integration` before release.

## Risks & rollback

- **Self-referential extras**: broadly supported (hatchling + modern pip); verification step 1
  catches any resolver issue before merge.
- **Dropping `ruff check .`**: pre-commit already enforces ruff in the same job — no coverage
  loss; verified by step 2.
- **RTD change**: verified by step 4 building the RTD way locally before merge.
- Rollback is a single revert of the PR; no runtime/library code changes are involved.

## Delivery (one PR, separated commits)

1. `refactor(deps): compose extras by reference; add build extra; move linters to pre-commit`
2. `refactor(docs): single-source Sphinx deps in pyproject; retire docs/requirements.txt`
3. `ci: install tools from declared extras; drop standalone ruff step`
4. `ci: normalize GitHub Actions versions across workflows`
5. `ci(dependabot): drop /docs entry, add update groups; add pre-commit autoupdate workflow`
