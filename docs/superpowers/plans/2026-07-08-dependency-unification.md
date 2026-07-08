# Dependency Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Declare every Python dependency and tool version exactly once (pyproject.toml as the single source), so CI and Read the Docs build from identical sources and Dependabot can see everything.

**Architecture:** pyproject extras compose by self-reference (hatchling backend); `docs/requirements.txt` is retired in favour of the `[docs]` extra; black/isort/ruff versions move entirely to `.pre-commit-config.yaml`; CI installs from declared extras; Dependabot is grouped and a weekly `pre-commit autoupdate` workflow covers the surface Dependabot cannot watch.

**Tech Stack:** Python ≥3.14, hatchling, pip extras, Sphinx, pre-commit, GitHub Actions, Dependabot, Read the Docs.

**Branch:** `refactor/unify-dependencies` (already created; spec committed at `f6c22c1`).

**Spec:** `docs/superpowers/specs/2026-07-08-dependency-unification-design.md`

## Global Constraints

- requires-python `>=3.14`; build backend is `hatchling`. Self-referential extras (`kibana-py[docs]`) are allowed.
- GitHub Actions are pinned by full commit SHA with a trailing `# vX.Y.Z` comment. Keep that style.
- Commits must be Conventional-Commit style AND carry the provenance trailer (pre-commit `commit-msg` hooks enforce both). Trailer to use:
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`
- Docs floors are reconciled to the newest already on main: `sphinx-copybutton>=0.5.2`, `sphinx-design>=0.7.0`, `sphinx-autobuild>=2025.8.25`.
- `all` is a FEATURE aggregate only (async+orjson+observability); it does NOT pull docs/dev/build.
- Do not bump sphinx/furo major versions in this work (deferred).
- Never `git add -A`; stage only the files named in each task.

---

### Task 1: Restructure `pyproject.toml` extras (declare once, compose by reference)

**Files:**
- Modify: `pyproject.toml` — the `[project.optional-dependencies]` table only.

**Interfaces:**
- Produces: extras `async`, `orjson`, `observability`, `docs`, `build`, `all`, `dev`. Later tasks and CI install `.[dev,all]`, `.[docs]`, `.[dev]`, `.[build]`.

- [ ] **Step 1: Replace the entire `[project.optional-dependencies]` table** with:

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
docs = [
    "sphinx>=7.0.0",
    "furo>=2024.1.0",
    "myst-parser>=2.0.0",
    "sphinx-copybutton>=0.5.2",
    "sphinx-design>=0.7.0",
    "sphinx-autobuild>=2025.8.25",
]
build = ["build", "twine>=6.2.0", "cyclonedx-bom"]
all = ["kibana-py[async,orjson,observability]"]
dev = [
    "pytest>=7.0",
    "pytest-cov",
    "pytest-mock",
    "pytest-asyncio",
    "mypy>=1.0",
    "pyright",
    "types-python-dateutil",
    "pip-audit>=2.0",
    "bandit>=1.7",
    "interrogate",
    "nox",
    "pre-commit>=3.0",
    "psutil>=5.0",
    "kibana-py[docs,build]",
]
```

Note vs. today: `black`/`isort`/`ruff` are GONE from `dev` (pre-commit owns them — Task not needed, they already live in `.pre-commit-config.yaml`); `interrogate` is ADDED; `build`/`twine` moved into `[build]`; docs deps referenced via `kibana-py[docs]` instead of re-listed.

- [ ] **Step 2: Verify the extras resolve** (apply into the existing venv):

Run: `.venv/bin/pip install -e ".[dev,all]"`
Expected: completes with no resolver error; installs `interrogate` and `cyclonedx-bom`.

- [ ] **Step 3: Verify the toolchain is intact**

Run:
```bash
.venv/bin/python -c "import build, twine, interrogate; print('build/twine/interrogate OK')"
.venv/bin/mypy kibana/
.venv/bin/pre-commit run --all-files
```
Expected: import line prints OK; mypy passes; pre-commit passes (black/isort/ruff run from the pinned hooks, proving they don't need to be in `dev`).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "refactor(deps): compose extras by reference; add build extra" \
  -m "all/dev now reference other extras instead of re-listing them; black/isort/ruff drop out of dev (pre-commit is their source); interrogate and cyclonedx-bom become declared, version-tracked deps via dev and the new build extra." \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Retire `docs/requirements.txt`; point RTD and docs cache at the single source

**Files:**
- Delete: `docs/requirements.txt`
- Modify: `.readthedocs.yaml` — the `python.install` block
- Modify: `.github/workflows/docs.yml` — the build-docs `cache-dependency-path`

**Interfaces:**
- Consumes: the `[docs]` extra from Task 1.

- [ ] **Step 1: Delete the redundant file**

Run: `git rm docs/requirements.txt`

- [ ] **Step 2: Repoint Read the Docs** — replace the `python:` block in `.readthedocs.yaml` with:

```yaml
python:
  install:
    - method: pip
      path: .
      extra_requirements:
        - docs
```

(Remove the `- requirements: docs/requirements.txt` line, the `extra_requirements: [dev]` install, and the now-unnecessary `post_install: - pip install -e .` job.)

- [ ] **Step 3: Fix the docs.yml pip cache key** — in `.github/workflows/docs.yml`, the build-docs step's `cache-dependency-path` currently lists two lines; change it to reference only `pyproject.toml`:

```yaml
          cache-dependency-path: |
            pyproject.toml
```

- [ ] **Step 4: Verify the docs build the RTD way** from the single source:

Run:
```bash
python3.14 -m venv /tmp/rtdcheck && /tmp/rtdcheck/bin/pip install ".[docs]"
/tmp/rtdcheck/bin/sphinx-build -W --keep-going -b html docs/source /tmp/rtdcheck-out
rm -rf /tmp/rtdcheck /tmp/rtdcheck-out
grep -rn "requirements.txt" .github/ .readthedocs.yaml || echo "NO requirements.txt references remain"
```
Expected: sphinx build succeeds with no warnings-as-errors; grep prints the "NO ... remain" line.

- [ ] **Step 5: Commit**

```bash
git add -u docs/requirements.txt .readthedocs.yaml .github/workflows/docs.yml
git commit -m "refactor(docs): single-source Sphinx deps in pyproject; retire docs/requirements.txt" \
  -m "Read the Docs and the docs.yml pip cache now use the pyproject [docs] extra, the same source CI and 'make docs' already use." \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: CI installs from declared extras; drop the standalone ruff step

**Files:**
- Modify: `.github/workflows/test.yml` (install line + remove ruff step)
- Modify: `.github/workflows/release.yml` (build install line)
- Modify: `.github/workflows/docs.yml` (quality-checks install)

**Interfaces:**
- Consumes: `dev`, `all`, `build` extras from Task 1.

- [ ] **Step 1: test.yml** — change the install step body from
  `pip install -e ".[dev,async,orjson,observability]"` to:

```yaml
          pip install -e ".[dev,all]"
```
Then DELETE the whole `- name: Lint with ruff` step (the `ruff check .` step); the job already runs `pre-commit run --all-files`, which includes ruff.

- [ ] **Step 2: release.yml** — change the build job install from
  `pip install build twine cyclonedx-bom` to:

```yaml
          pip install ".[build]"
```

- [ ] **Step 3: docs.yml quality-checks** — replace the two install lines
  (`pip install -e .` and `pip install interrogate`) with a single:

```yaml
          pip install -e ".[dev]"
```

- [ ] **Step 4: Verify** the extras cover what the jobs need, and YAML is valid:

Run:
```bash
.venv/bin/interrogate --version && echo "interrogate from dev OK"
python3 -c "import yaml; [yaml.safe_load(open(f)) for f in ['.github/workflows/test.yml','.github/workflows/release.yml','.github/workflows/docs.yml']]; print('workflows parse OK')"
grep -n "ruff check" .github/workflows/test.yml && echo "STILL PRESENT (bad)" || echo "ruff step removed OK"
```
Expected: interrogate prints a version; workflows parse; "ruff step removed OK".

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/test.yml .github/workflows/release.yml .github/workflows/docs.yml
git commit -m "ci: install tools from declared extras; drop standalone ruff step" \
  -m "test.yml uses .[dev,all] (one spelling, matches Makefile/nox) and relies on pre-commit for ruff; release build uses .[build]; docs quality-checks uses .[dev] for interrogate. No more ad-hoc unpinned pip installs." \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Normalize GitHub Actions versions across all workflows

**Files:**
- Modify: `.github/workflows/release.yml` (the lagging pins)
- (Confirm consistency in `test.yml`, `checks.yml`, `docs.yml` — already current.)

**Context:** release.yml lags; other workflows are current. Targets — the SHAs already proven on main for the first three, and the Dependabot-proposed SHAs for the last two.

- [ ] **Step 1: Pull the two new-major SHAs from the open Dependabot PRs** (source of truth for the exact pins):

Run:
```bash
gh pr diff 5 | grep "download-artifact@"   # -> download-artifact v8 SHA
gh pr diff 6 | grep "action-gh-release@"   # -> action-gh-release v3 SHA
```
Record the `<sha> # vX` for each.

- [ ] **Step 2: In `release.yml`, replace each pin** with the unified target:

| Action | Old (release.yml) | New target |
|---|---|---|
| actions/checkout | `@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4` | `@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2` |
| actions/setup-python | `@a26af69be951a213d495a4c3e4e4022e16d87065 # v5` | `@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0` |
| actions/upload-artifact | `@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4` | `@bbbca2ddaa5d8feaa63e36b76fdaad77386f024f # v7.0.0` |
| actions/download-artifact | `@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4` (x2) | v8 SHA from Step 1 |
| softprops/action-gh-release | `@3bb12739c298aeb8a4eeaf626c5b8d85266b0e65 # v2` | v3 SHA from Step 1 |

(Leave `pypa/gh-action-pypi-publish@... # release/v1` unchanged — not Dependabot-managed here.)

- [ ] **Step 3: Verify each action now has ONE pin repo-wide:**

Run:
```bash
grep -rhoE "(actions/(checkout|setup-python|upload-artifact|download-artifact)|softprops/action-gh-release)@[a-f0-9]+ # [^ ]+" .github/workflows/ | sort -u
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml')); print('release.yml parses OK')"
```
Expected: exactly one line per action name; release.yml parses.

- [ ] **Step 4: Commit** (note the release-time caveat in the body)

```bash
git add .github/workflows/release.yml
git commit -m "ci: normalize GitHub Actions versions across workflows" \
  -m "release.yml was lagging (checkout v4, setup-python v5, artifact v4, gh-release v2); align to the versions used elsewhere plus the Dependabot-proposed majors. release.yml runs only at tag time, so its changes are not exercised by PR CI — watch the next release (or dry-run) to confirm the artifact/gh-release majors behave." \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Dependabot grouping + drop `/docs`; add pre-commit autoupdate workflow

**Files:**
- Modify: `.github/dependabot.yml`
- Create: `.github/workflows/pre-commit-autoupdate.yml`

- [ ] **Step 1: Rewrite `.github/dependabot.yml`** as (removes `/docs`, adds groups):

```yaml
version: 2
updates:
  - package-ecosystem: pip
    directory: "/"
    schedule:
      interval: weekly
      day: monday
    groups:
      python-dependencies:
        patterns:
          - "*"

  - package-ecosystem: github-actions
    directory: "/"
    schedule:
      interval: weekly
      day: monday
    groups:
      github-actions:
        patterns:
          - "*"
```

- [ ] **Step 2: Resolve the create-pull-request action SHA** for pinning:

Run: `gh api repos/peter-evans/create-pull-request/git/refs/tags/v7 --jq .object.sha 2>/dev/null || echo "resolve latest v7 tag SHA manually"`
Record `<sha> # v7`.

- [ ] **Step 3: Create `.github/workflows/pre-commit-autoupdate.yml`:**

```yaml
name: pre-commit autoupdate

on:
  schedule:
    - cron: "0 6 * * 1"  # Mondays 06:00 UTC
  workflow_dispatch:

permissions: {}

jobs:
  autoupdate:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      pull-requests: write
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: "3.14"
      - run: python -m pip install --upgrade pre-commit
      - run: pre-commit autoupdate
      - uses: peter-evans/create-pull-request@<SHA-FROM-STEP-2> # v7
        with:
          commit-message: "ci(pre-commit): autoupdate hook versions"
          title: "ci(pre-commit): autoupdate hook versions"
          body: "Automated weekly `pre-commit autoupdate`. Review the rev bumps before merging."
          branch: chore/pre-commit-autoupdate
          base: main
          labels: dependencies
```

- [ ] **Step 4: Verify both files parse:**

Run: `python3 -c "import yaml; yaml.safe_load(open('.github/dependabot.yml')); yaml.safe_load(open('.github/workflows/pre-commit-autoupdate.yml')); print('OK')"`
Expected: prints OK. (Confirm the `<SHA-FROM-STEP-2>` placeholder was replaced with the real SHA.)

- [ ] **Step 5: Commit**

```bash
git add .github/dependabot.yml .github/workflows/pre-commit-autoupdate.yml
git commit -m "ci(dependabot): group updates, drop dead /docs entry; add pre-commit autoupdate" \
  -m "docs/requirements.txt is gone so the pip /docs Dependabot entry is removed; pip and github-actions updates are grouped into one PR each. A weekly pre-commit autoupdate workflow bumps hook revs, covering the one surface Dependabot cannot watch." \
  -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Deliver — full local gate, PR, close superseded Dependabot PRs, verify CI

**Files:** none (delivery only).

- [ ] **Step 1: Full local gate from a clean environment**

Run:
```bash
make clean-all && make setup PYTHON=python3.14 && make check && make docs
```
Expected: setup succeeds (extras resolve), `make check` passes (pre-commit + mypy + audit + sast + unit tests), `make docs` builds HTML + linkcheck.

- [ ] **Step 2: Push and open the PR**

```bash
git push -u origin refactor/unify-dependencies
gh pr create --base main --head refactor/unify-dependencies \
  --title "Unify dependency declarations (single-source pyproject; retire docs/requirements.txt; group Dependabot)" \
  --body-file - <<'EOF'
Implements docs/superpowers/specs/2026-07-08-dependency-unification-design.md.

- pyproject is the single source; extras compose by reference; new [build] extra.
- docs/requirements.txt retired; RTD + docs cache use the [docs] extra.
- black/isort/ruff versions owned solely by pre-commit; CI drops standalone `ruff check .`.
- CI installs from declared extras; Actions versions normalized.
- Dependabot grouped, `/docs` entry dropped; weekly pre-commit autoupdate added.

Closes #2, #3, #4, #5, #6 (Actions bumps folded into the normalization) and #8, #9
(sphinx/furo majors target the retired requirements.txt; revisit in [docs] separately).

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01RwzKGJmowSpMiUiUjUrzfx
EOF
```

- [ ] **Step 2b: STOP — confirm with the human before closing any PRs.** Closing PRs is outward-facing; get an explicit go-ahead, then:

```bash
for n in 2 3 4 5 6; do gh pr close $n --comment "Superseded: Actions versions normalized consistently in #<THIS_PR>."; done
for n in 8 9; do gh pr close $n --comment "Superseded: docs/requirements.txt retired in #<THIS_PR>; sphinx/furo major bumps to be revisited against the pyproject [docs] extra."; done
```

- [ ] **Step 3: Watch CI to green**

Run: `gh pr checks <THIS_PR> --watch --interval 20`
Expected: all checks pass. If red, stop and diagnose (systematic-debugging).

- [ ] **Step 4: Report** the PR URL, CI result, and the list of closed PRs.

---

## Self-Review

**Spec coverage:**
- §1 pyproject single-source → Task 1 ✓
- §2 retire requirements.txt + RTD + docs.yml cache → Task 2 ✓
- §3 linters in pre-commit (remove from dev; drop `ruff check .`) → Task 1 (removal) + Task 3 (drop step) ✓
- §4 CI installs from extras (lean checks.yml unchanged) → Task 3 ✓ (checks.yml intentionally untouched)
- §5 Dependabot groups + drop /docs + normalize Actions + pre-commit autoupdate → Tasks 4 & 5 ✓
- §6 verification → Task 6 ✓
- Open-PR disposition (#2–#6, #8/#9) → Task 6 Step 2b ✓

**Placeholder scan:** The only intentional fill-ins are the two Dependabot SHAs (Task 4 Step 1) and the create-pull-request SHA (Task 5 Step 2), each with an exact command to resolve them — not vague placeholders.

**Consistency:** extra names (`dev`, `all`, `docs`, `build`) are used identically across Tasks 1/3/6; `.[dev,all]` is the single install spelling for the full env.
