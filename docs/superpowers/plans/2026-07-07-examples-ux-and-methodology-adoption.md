# kibana-py 0.3.1 — Examples UX + Methodology/git-controls Adoption — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every example human-runnable (watch → keep-or-clean, non-colliding resources, safe re-runs), fix a blocking `utils.py` SyntaxError, adopt the `agent-methodology` pack, and harden git-controls (SHA-pin the PyPI publisher) — then release `0.3.1`.

**Architecture:** Three sequenced workstreams landing as separate commits — **A** git-controls (first, so its commit discipline gates the rest), **B** vendored methodology install, **C** the examples rework (the `0.3.1` release content) — followed by a live verification pass captured as an evidence artifact. A and B are repo-only (excluded from wheel/sdist), so only C affects the shipped package; the version is a patch regardless.

**Tech Stack:** Python 3.14, hatchling, pytest, pre-commit (black/isort/ruff + new hooks), GitHub Actions, POSIX-sh validators, the `kibana`/`AsyncKibana` clients against a local `elastic-start-local` stack.

## Global Constraints

- **Target version:** `0.3.1` (patch). Bump `__versionstr__` in `kibana/_version.py`. A and B do **not** justify a version bump on their own; only C is release content.
- **Never touch `kibana/` library code or the public API** in this plan. If a change seems to require it, stop and escalate — it would change the semver calculus.
- **Python 3.14+**, `requires-python = ">=3.14"`. Use 3.14 syntax; no Python-2 constructs.
- **Resource naming:** every server resource an example creates is named `kbnpy-<example-slug>-<resource>`, where `<slug>` is derived from the filename via `resource_prefix(__file__)` (strip a trailing `_management`). Never a generic `kbnpy-example-*`.
- **Own-only-your-scope teardown:** an example's cleanup and idempotent pre-delete operate **only** on ids under its own `kbnpy-<slug>-*` namespace — never a broad glob, never user data.
- **Reversible by default:** deletion is gated behind explicit `y` / `--cleanup`; the default (bare Enter or no TTY) is **keep**.
- **Commits:** conventional-prefix + a provenance trailer (the agent's `Co-Authored-By:` satisfies it). Split by reason. Leave uncommitted until the user wants to inspect. Add an `Evidence:` trailer to the commit whose correctness rests on the live run.
- **Specs of record:** `docs/superpowers/specs/2026-07-07-examples-human-usable-cleanup-design.md` (v0.2, workstream C) and `docs/superpowers/specs/2026-07-07-adopt-methodology-and-git-controls-design.md` (v0.1, workstreams A+B). Reconcile a spec onto shipped code + bump its version if implementation diverges.

---

## Phase A — git-controls hardening (additive merge)

> Lands first so conventional-prefix + trailer + secret hooks gate workstreams B and C. **Merge into** existing config; do not clobber `test.yml`/`docs.yml` or the black/isort/ruff hooks.

### Task A1: Vendor the check scripts and tighten `.gitignore`

**Files:**
- Create: `scripts/checks/check-no-tracked-secrets.sh`
- Create: `scripts/checks/check-commit-trailer.sh`
- Modify: `.gitignore`

- [ ] **Step 1: Create `scripts/checks/check-no-tracked-secrets.sh`** (from `git-controls-starter`, verbatim)

```sh
#!/bin/sh
# Fail if a secret-looking file is TRACKED by git. Defense-in-depth beyond .gitignore:
# gitignore does nothing for a file committed *before* it was ignored. Fail closed. POSIX sh.
set -u
hits=$(git ls-files \
  | grep -E '(^|/)(\.env(\..+)?|.+\.pem|.+\.key|.+\.p12|id_rsa|id_ed25519|credentials\.json|service-account.*\.json|.+\.tfvars(\..+)?|.+\.tfstate(\..+)?)$' \
  | grep -vE '\.example$' || true)
if [ -n "$hits" ]; then
  echo "FAIL: secret-looking file(s) tracked by git — untrack, rotate the secret, and gitignore it:"
  printf '  %s\n' $hits
  exit 1
fi
echo "ok: no secret-looking files tracked"
exit 0
```

- [ ] **Step 2: Create `scripts/checks/check-commit-trailer.sh`** (verbatim), then make both executable

```sh
#!/bin/sh
# commit-msg hook: require a provenance/evidence trailer in the commit body.
# $1 = path to the commit message file. POSIX sh; uses git interpret-trailers.
set -u
msg="${1:?usage: check-commit-trailer.sh <commit-msg-file>}"
if git interpret-trailers --parse < "$msg" \
   | grep -qiE '^(Signed-off-by|Co-Authored-By|Evidence|Refs|Verified-by):'; then
  exit 0
fi
echo "FAIL: commit message needs a provenance trailer in the body, e.g.:"
echo "  Signed-off-by: Name <email>  (add with: git commit -s)"
echo "  Co-Authored-By: Name <email>   |   Evidence: <path-or-url>   |   Refs: <issue>"
exit 1
```

Run: `chmod +x scripts/checks/*.sh`

- [ ] **Step 3: Tighten `.gitignore`** — replace the bare `.env` line (currently line 103) with a glob + allowlist. Find:

```
.env
```

Replace with:

```
# Secret-bearing env files are un-committable by pattern; only templates are allowed back in.
.env
.env.*
!.env.example
!*.env.example
```

(The existing `elastic-start-local/.env.local` ignore at line 3 stays; `.env.otel.example` remains tracked because of the `!*.env.example` allowlist — verify in Step 4.)

- [ ] **Step 4: Verify the secret hook passes against the current tree and the allowlist holds**

Run: `sh scripts/checks/check-no-tracked-secrets.sh && git check-ignore -v elastic-start-local/.env.local ; git ls-files --error-unmatch .env.otel.example`
Expected: `ok: no secret-looking files tracked`; `.env.local` reported ignored; `.env.otel.example` still tracked (no error).

- [ ] **Step 5: Commit**

```bash
git add scripts/checks/ .gitignore
git commit -m "ci: vendor git-controls secret/trailer validators; tighten .env gitignore

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task A2: Extend `.pre-commit-config.yaml` (merge new hooks)

**Files:**
- Modify: `.pre-commit-config.yaml`

**Interfaces:**
- Consumes: the two scripts from A1.
- Produces: a config that installs the `commit-msg` stage and enforces conventional prefix + trailer + secret scanning, alongside the untouched black/isort/ruff hooks.

- [ ] **Step 1: Add hook-type + version keys** at the top of `.pre-commit-config.yaml`, immediately after the header comment and before `exclude:`

```yaml
default_install_hook_types: [pre-commit, commit-msg]
minimum_pre_commit_version: "3.5.0"
```

- [ ] **Step 2: Extend the `pre-commit-hooks` block** (currently rev `v4.6.0`, ids trailing-whitespace…check-added-large-files) — add four hooks under its `hooks:` list, keeping the existing five:

```yaml
      - id: mixed-line-ending
        args: ["--fix=lf"]
      - id: check-merge-conflict
      - id: check-case-conflict
      - id: detect-private-key
```

- [ ] **Step 3: Append the conventional-commit and local hooks** as new `repos:` entries at the end of the file (after the ruff block). Leave black/isort/ruff exactly as they are.

```yaml
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: v4.4.0
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
        args: [feat, fix, docs, chore, refactor, test, build, ci, perf, style, revert]

  - repo: local
    hooks:
      - id: check-no-tracked-secrets
        name: "no secret-looking file is tracked by git"
        language: script
        entry: scripts/checks/check-no-tracked-secrets.sh
        pass_filenames: false
      - id: check-commit-trailer
        name: "commit body carries a provenance trailer"
        language: script
        entry: scripts/checks/check-commit-trailer.sh
        stages: [commit-msg]
```

- [ ] **Step 4: Install the hooks and run the file-stage checks**

Run: `pre-commit install --install-hooks && pre-commit run --all-files`
Expected: black/isort/ruff/hygiene/detect-private-key/check-no-tracked-secrets all pass (or auto-fix then pass on re-run). `conventional-pre-commit` and `check-commit-trailer` do not run here (commit-msg stage only).

- [ ] **Step 5: Commit** (this commit itself must satisfy the new gate)

```bash
git add .pre-commit-config.yaml
git commit -m "ci: enforce conventional commits, provenance trailer, private-key scan

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task A3: Prove the commit-message gate actually gates

> `grounded-verifiable-gates`: a gate everything passes is decoration. Prove rejection AND acceptance. No files committed; this is a live check of the hooks from A2.

- [ ] **Step 1: A non-conforming subject is rejected**

Run: `git commit --allow-empty -m "just some words" 2>&1 | tail -3 ; echo "exit=$?"`
Expected: `conventional-pre-commit` fails the commit (non-zero); no commit is created.

- [ ] **Step 2: A conforming subject with no trailer is rejected**

Run: `git commit --allow-empty -m "chore: no trailer here" 2>&1 | tail -3 ; echo "exit=$?"`
Expected: `check-commit-trailer` fails with the "needs a provenance trailer" message; no commit created.

- [ ] **Step 3: A conforming subject WITH a trailer passes, then undo it**

Run:
```bash
git commit --allow-empty -m "chore: gate self-test

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && git reset --hard HEAD~1
```
Expected: commit succeeds, then is removed. Records that the gate discriminates (fails bad, passes good).

### Task A4: SHA-pin `release.yml`

**Files:**
- Modify: `.github/workflows/release.yml`

> Surgical: pin each action to a full commit SHA at its **current** major (no functional version bumps before publish). SHAs resolved 2026-07-07; Dependabot (already tracking `github-actions`) keeps them fresh.

- [ ] **Step 1: Replace every mutable `uses:` ref** in `.github/workflows/release.yml` with its pinned SHA:

| Current | Pinned |
|---|---|
| `actions/checkout@v4` | `actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4` |
| `actions/setup-python@v5` | `actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5` |
| `actions/upload-artifact@v4` | `actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02 # v4` |
| `actions/download-artifact@v4` | `actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093 # v4` |
| `softprops/action-gh-release@v2` | `softprops/action-gh-release@3bb12739c298aeb8a4eeaf626c5b8d85266b0e65 # v2` |
| `pypa/gh-action-pypi-publish@release/v1` | `pypa/gh-action-pypi-publish@cef221092ed1bacb1cc03d23a2d87d1d172e277b # release/v1` |

(There are two `actions/download-artifact` and two `actions/checkout` occurrences — pin all of them.)

- [ ] **Step 2: Verify no mutable ref remains**

Run: `grep -nE 'uses: .+@(v[0-9]+|release/|main|master)$' .github/workflows/release.yml ; echo "remaining=$?"`
Expected: no matches (`remaining=1`). Every `uses:` now ends in a 40-hex SHA with a `# vX` comment.

- [ ] **Step 3: Confirm YAML still parses**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release.yml')); print('ok')"`
Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: SHA-pin release.yml actions to guard the PyPI publish

Pin checkout/setup-python/upload+download-artifact/gh-release/pypi-publish to
full commit SHAs so a moved tag can't change what runs at publish time.
Dependabot (github-actions) keeps the pins fresh.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task A5: Add `checks.yml` — local == CI

**Files:**
- Create: `.github/workflows/checks.yml`

> Re-runs the same `.pre-commit-config.yaml` in CI so local hooks and CI can't drift. Hardened to match `test.yml`. commit-msg hooks are local-only (the agreed default); this runs the file stage.

- [ ] **Step 1: Create `.github/workflows/checks.yml`** (SHAs reused from `test.yml`)

```yaml
name: checks
on:
  push:
    branches: [main]
  pull_request:

permissions: {}  # deny-all at workflow level; grant per-job
concurrency:
  group: checks-${{ github.ref }}
  cancel-in-progress: true

jobs:
  pre-commit:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    permissions:
      contents: read
    steps:
      - uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
      - uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
        with:
          python-version: "3.14"
      - run: python -m pip install --upgrade pre-commit
      - run: pre-commit run --all-files --show-diff-on-failure
```

- [ ] **Step 2: Verify it parses and pins by SHA**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/checks.yml')); print('ok')" && grep -cE 'uses: .+@[0-9a-f]{40} #' .github/workflows/checks.yml`
Expected: `ok` then `2`.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/checks.yml
git commit -m "ci: run pre-commit in CI so local and CI can't drift

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task A6: Vendor `bootstrap.sh`

**Files:**
- Create: `bootstrap.sh`

- [ ] **Step 1: Create `bootstrap.sh`** (from `git-controls-starter`, verbatim) and `chmod +x bootstrap.sh`

```sh
#!/bin/sh
# One-command setup: get pre-commit and install the git hooks, without polluting your system.
#   1. prek — single static binary, zero Python   2. pre-commit on PATH   3. local .venv
# Usage:  ./bootstrap.sh
set -eu
PRECOMMIT_VERSION="4.6.0"
if command -v prek >/dev/null 2>&1; then
  echo "==> using prek (no Python needed)"; prek install --install-hooks; prek run --all-files; exit 0
fi
if command -v pre-commit >/dev/null 2>&1; then
  echo "==> using pre-commit on PATH ($(pre-commit --version))"; pre-commit install --install-hooks; pre-commit run --all-files; exit 0
fi
echo "==> no prek/pre-commit found — bootstrapping a local .venv"
if ! command -v python3 >/dev/null 2>&1; then
  echo "error: need python3, or install prek (https://github.com/j178/prek) and re-run." >&2; exit 1
fi
python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet "pre-commit==${PRECOMMIT_VERSION}"
.venv/bin/pre-commit install --install-hooks
.venv/bin/pre-commit run --all-files
echo ""; echo "Done. Hooks installed; they run on every commit."
```

- [ ] **Step 2: Verify it is valid POSIX sh**

Run: `sh -n bootstrap.sh && echo ok`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add bootstrap.sh
git commit -m "chore: add bootstrap.sh for one-command hook setup

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task A7: Reconcile `CONTRIBUTING.md` commit guidance

**Files:**
- Modify: `CONTRIBUTING.md` (the "Commit with a descriptive message" section around lines 150-160)

> `docs-as-deliverable` + `configuration-single-source-of-truth`: the doc must match the enforced hooks and what history already does (`feat:`/`fix:`/`docs:`).

- [ ] **Step 1: Replace the commit-message guidance.** Find the block:

```
# Commit with a descriptive message
git commit -m "Add feature: description of your changes"
```

Follow these commit message guidelines:
- Use present tense ("Add feature" not "Added feature")
- Use imperative mood ("Move cursor to..." not "Moves cursor to...")
- Limit first line to 72 characters
- Reference issues and pull requests when relevant
```

Replace with:

````
# Commit with a Conventional-Commit subject and a provenance trailer
git commit -s -m "feat: description of your change"
```

Commit messages are machine-checked by pre-commit (`conventional-pre-commit` + a
trailer hook). Each commit must:

- Start with a Conventional-Commit type prefix — one of
  `feat, fix, docs, chore, refactor, test, build, ci, perf, style, revert`
  (e.g. `fix(examples): repair cleanup ordering`).
- Use present tense, imperative mood; keep the subject under ~72 characters.
- Carry a provenance trailer in the body — the simplest is `git commit -s`
  (a `Signed-off-by:`), which also satisfies the [DCO](https://developercertificate.org/).
  `Co-Authored-By:`, `Refs:`, and `Evidence:` (a link to a captured test/run) also
  satisfy it. When a commit's correctness rests on a run, add
  `Evidence: <path-or-url>` so the proof travels with the commit.
- Reference issues/PRs when relevant.

Run `./bootstrap.sh` once to install the hooks locally; CI re-runs the same
config (`.github/workflows/checks.yml`).
````

- [ ] **Step 2: Verify markdown still lints / the section reads correctly**

Run: `grep -n "Conventional-Commit" CONTRIBUTING.md`
Expected: the new guidance is present.

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: reconcile CONTRIBUTING commit guidance with the enforced hooks

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase B — methodology pack (vendored copy)

> Single source: copy from a local checkout of `pedro-angel/agent-methodology`. Do **not** copy its `templates/git-controls/` (Phase A is the git-controls source).

### Task B1: Vendor `AGENTS.md`, `skills/`, `CLAUDE.md`, and `.claude/skills/`

**Files:**
- Create: `AGENTS.md`, `CLAUDE.md`, `skills/<slug>/SKILL.md` (15 skills), `.claude/skills/<slug>/SKILL.md`

- [ ] **Step 1: Clone the pack to a temp location** (skip if already available)

Run: `git clone --depth 1 https://github.com/pedro-angel/agent-methodology /tmp/agent-methodology`
Expected: clone succeeds.

- [ ] **Step 2: Copy the source of truth, the Claude adapter, and the skills into the repo root**

Run:
```bash
cp /tmp/agent-methodology/AGENTS.md ./AGENTS.md
cp /tmp/agent-methodology/adapters/claude/CLAUDE.md ./CLAUDE.md
cp -R /tmp/agent-methodology/skills ./skills
```

- [ ] **Step 3: Copy the skills into `.claude/skills/` for native slash-skill discovery**

Run: `mkdir -p .claude/skills && cp -R /tmp/agent-methodology/skills/. .claude/skills/`

- [ ] **Step 4: Verify the expected files landed (all 15 skills, both locations)**

Run: `ls skills | wc -l ; ls .claude/skills | wc -l ; test -f AGENTS.md && test -f CLAUDE.md && echo "roots ok"`
Expected: `15`, `15`, `roots ok`.

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md CLAUDE.md skills .claude/skills
git commit -m "docs: adopt agent-methodology (AGENTS.md + skills + Claude adapter)

Vendored from pedro-angel/agent-methodology; git-controls installed separately
in Phase A (its templates/git-controls is intentionally not copied).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task B2: Verify the methodology doesn't leak into the shipped package

**Files:** none (verification only)

- [ ] **Step 1: Build sdist + wheel**

Run: `python -m build 2>/dev/null || pip install build && python -m build`
Expected: `dist/kibana_py-*.whl` and `dist/kibana-py-*.tar.gz` produced.

- [ ] **Step 2: Confirm `AGENTS.md`/`skills/`/`.github` are absent from both artifacts**

Run:
```bash
python -m zipfile -l dist/kibana_py-*.whl | grep -E "AGENTS|skills/|\.github|CLAUDE" && echo "LEAK" || echo "wheel clean"
tar tzf dist/kibana-py-*.tar.gz | grep -E "AGENTS|skills/|CLAUDE" && echo "LEAK" || echo "sdist clean"
```
Expected: `wheel clean` and `sdist clean` (the sdist include-list and wheel `packages=["kibana"]` already exclude them).

- [ ] **Step 3: Clean up build artifacts** (no commit)

Run: `rm -rf dist build *.egg-info`

---

## Phase C — Examples UX rework (the `0.3.1` release content)

> Foundation tasks (C1–C2) first; per-file conversion tasks (C3+) are grounded in the audit in `docs/superpowers/notes/2026-07-07-examples-audit.md` and are appended below. C touches only `examples/`, `README`, `CHANGELOG`, and `kibana/_version.py`.

### Task C1: Fix the blocking `utils.py` SyntaxError

**Files:**
- Modify: `examples/utils.py` — `_get_opentelemetry_version()` (lines ~321-344)

**Interfaces:**
- Produces: an importable `examples/utils.py` (every example does `from utils import …`).

- [ ] **Step 1: Confirm the current failure**

Run: `python -m py_compile examples/utils.py ; echo "exit=$?"`
Expected: `SyntaxError: multiple exception types must be parenthesized` at line 329; `exit=1`.

- [ ] **Step 2: Rewrite `_get_opentelemetry_version()`** — replace the whole function body's broken `except ImportError, X:` chain with correct single-type fallbacks:

```python
def _get_opentelemetry_version() -> str:
    """Get the OpenTelemetry SDK version."""
    import importlib.metadata

    for pkg in ("opentelemetry-sdk", "opentelemetry-api"):
        try:
            return importlib.metadata.version(pkg)
        except Exception:
            continue
    try:
        from opentelemetry import __version__

        return __version__
    except Exception:
        return "unknown"
```

- [ ] **Step 3: Verify it compiles and imports**

Run: `python -m py_compile examples/utils.py && python -c "import sys; sys.path.insert(0,'examples'); import utils; print('import ok')"`
Expected: `import ok`.

- [ ] **Step 4: Commit**

```bash
git add examples/utils.py
git commit -m "fix(examples): repair Python-2 except syntax in utils.py

except ImportError, X: is a SyntaxError under 3.14, breaking import utils and
therefore every example. Collapse to correct single-type fallbacks.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task C2: Add example helpers to `utils.py` (naming, keep-summary, TTY-safe prompt)

**Files:**
- Modify: `examples/utils.py` (add helpers; harden `should_cleanup()`)
- Test: `examples/tests/test_example_utils.py` (new)

**Interfaces:**
- Produces:
  - `resource_prefix(file: str) -> str` → `"kbnpy-<stem>"` with a trailing `_management` stripped from the filename stem.
  - `print_kept(created: list[tuple[str, str]]) -> None` → prints a consistent "Kept … re-run with --cleanup to remove" summary.
  - `should_cleanup(prompt: str = ...) -> bool` → unchanged flag behavior, but returns `False` (keep) without prompting when stdin is not a TTY.

- [ ] **Step 1: Write the failing tests**

```python
# examples/tests/test_example_utils.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils  # noqa: E402


def test_resource_prefix_strips_management_suffix():
    assert utils.resource_prefix("/x/lists_management.py") == "kbnpy-lists"
    assert utils.resource_prefix("/x/simple_status.py") == "kbnpy-simple-status"


def test_should_cleanup_no_tty_defaults_keep(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["ex.py"])  # no flags
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert utils.should_cleanup() is False


def test_should_cleanup_flags_win(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["ex.py", "--cleanup"])
    assert utils.should_cleanup() is True
    monkeypatch.setattr(sys, "argv", ["ex.py", "--no-cleanup"])
    assert utils.should_cleanup() is False


def test_print_kept_smoke(capsys):
    utils.print_kept([("list", "kbnpy-lists-bad-ips")])
    assert "kbnpy-lists-bad-ips" in capsys.readouterr().out
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest examples/tests/test_example_utils.py -v`
Expected: FAIL (`resource_prefix`/`print_kept` undefined; `should_cleanup` prompts).

- [ ] **Step 3: Add the helpers to `examples/utils.py`** and harden `should_cleanup()`

```python
def resource_prefix(file: str) -> str:
    """Return the per-example resource namespace ``kbnpy-<stem>`` derived from a filename.

    The stem is the filename without extension, with a trailing ``_management``
    removed and underscores normalised to hyphens, so ``lists_management.py`` →
    ``kbnpy-lists``. This is the single source of the example's resource namespace.
    """
    stem = Path(file).stem
    if stem.endswith("_management"):
        stem = stem[: -len("_management")]
    return "kbnpy-" + stem.replace("_", "-")


def print_kept(created: list[tuple[str, str]]) -> None:
    """Print a consistent summary of resources left behind when the user keeps them."""
    if not created:
        return
    print("\nKept the following resources (re-run with --cleanup to remove):")
    for kind, ident in created:
        print(f"  - {kind}: {ident}")
```

Then modify `should_cleanup()` — add a no-TTY guard before the `input()` call:

```python
    if "--cleanup" in sys.argv:
        return True
    if "--no-cleanup" in sys.argv:
        return False
    if not sys.stdin.isatty():
        print("Non-interactive (no TTY): keeping created resources. "
              "Pass --cleanup to delete them.")
        return False
    return input(prompt).lower().strip() == "y"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest examples/tests/test_example_utils.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add examples/utils.py examples/tests/test_example_utils.py
git commit -m "feat(examples): add resource_prefix/print_kept helpers and TTY-safe should_cleanup

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task C3: Establish the canonical conversion pattern on `lists_management.py`

**Files:**
- Modify: `examples/lists_management.py`

**Interfaces:**
- Consumes: `resource_prefix`, `should_cleanup`, `print_kept` from C2.
- Produces: the reference before→after every other C task copies. **Read this task before C4–C10.**

> This is the standard transform. Every creating example gets exactly these five changes:
> (1) import the helpers; (2) derive `PREFIX = resource_prefix(__file__)` and build ids off it;
> (3) idempotent pre-delete before each create (own-scope only); (4) track created ids;
> (5) `finally:` gates teardown behind `should_cleanup()`, else `print_kept()`.

- [ ] **Step 1: Apply the transform.** Change the imports, id, and the try/finally:

```python
from utils import get_kibana_config, print_kept, resource_prefix, should_cleanup

from kibana import Kibana
from kibana.exceptions import NotFoundError


def main():
    kibana_url, basic_auth, api_key = get_kibana_config()
    client = Kibana(kibana_url, api_key=api_key) if api_key else Kibana(kibana_url, basic_auth=basic_auth)

    prefix = resource_prefix(__file__)          # "kbnpy-lists"
    list_id = f"{prefix}-bad-ips"
    created: list[tuple[str, str]] = []
    try:
        # value-list data streams are shared infra — create only if missing, never torn down
        try:
            status = client.lists.get_index_status()
        except NotFoundError:
            client.lists.create_index()
            status = client.lists.get_index_status()
        print(f"Value list data streams ready: {status.body}")

        # idempotent start: clear only THIS example's own prior resource, then create fresh
        try:
            client.lists.delete(id=list_id)
        except NotFoundError:
            pass
        created_list = client.lists.create(
            name="Bad IPs (kibana-py example)", description="Known bad IP addresses",
            type="ip", id=list_id,
        )
        created.append(("value list", list_id))
        print(f"Created list {created_list.body['id']} (type={created_list.body['type']})")

        # ... existing create_item / import_items / find_items / export_items steps unchanged ...
    finally:
        if should_cleanup():
            try:
                client.lists.delete(id=list_id)   # deleting the list cascades to its items
                print(f"Deleted list {list_id}")
            except NotFoundError:
                pass
        else:
            print_kept(created)
        client.close()
```

- [ ] **Step 2: Compile-check**

Run: `python -m py_compile examples/lists_management.py && echo ok`
Expected: `ok`

- [ ] **Step 3: Live-run all modes** (stack must be up)

Run:
```bash
python examples/lists_management.py --no-cleanup
python examples/lists_management.py --no-cleanup   # re-run: must NOT 409
python examples/lists_management.py --cleanup
echo "" | python examples/lists_management.py       # no-TTY: keeps, no crash
```
Expected: no `409`/`ConflictError`; final `--cleanup` deletes; piped run prints the keep notice.

- [ ] **Step 4: Commit**

```bash
git add examples/lists_management.py
git commit -m "refactor(examples): keep/clean + namespacing pattern (lists reference)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Tasks C4–C10: Apply the C3 transform across the remaining examples

> **Row-level detail for every file — its current ids, create/delete calls, and gotchas — is in
> `docs/superpowers/notes/2026-07-07-examples-audit.md`. Consult the matching row before editing a file.**
> Execution may fan out per-file within a task (`parallel-agent-fan-out`): give each agent a
> disjoint file, namespace-only its own resources, and re-run each file's `py_compile` + a live
> run yourself against the merged tree. Each task below ends with a compile check of its whole
> batch, a representative live run, and one commit.

#### Task C4: Simple `finally`-unconditional creators (single/low-complexity)

**Files (modify each):** `alerting_management.py`, `apm_management.py`, `cases_management.py`,
`connectors_management.py`, `dashboards_management.py`, `data_views_management.py`,
`detection_engine_management.py`, `endpoint_management.py`, `exception_lists_management.py`,
`logstash_management.py`, `saved_objects_management.py`, `security_management.py`,
`short_urls_management.py`, `slos_management.py`, `visualizations_management.py`,
`workflows_management.py`

- [ ] **Step 1:** Apply the C3 transform to each: import helpers, `prefix = resource_prefix(__file__)`, rebuild every literal id as `f"{prefix}-<resource>"` (replacing `kbnpy-example-*`), add idempotent pre-delete per created resource, track ids in `created`, and gate the existing `finally` delete behind `should_cleanup()` with `print_kept(created)` on keep.
- [ ] **Step 2: Per-file deltas from the audit (do not skip):**
  - `apm_management.py`: the **deployment annotation has no delete API** — it leaks to `observability-annotations` every run. Do not attempt to delete it; keep it as the sole non-namespaced side effect and print a one-line note that it can't be torn down. Agent config uses `create_or_update` (upsert) — safe to re-run.
  - `saved_objects_management.py`: step 5 deletes the dashboard mid-script and restores it via `import_objects(overwrite=True)`; step 6 forces conflicts then resolves — preserve that round trip; only the final teardown moves under the gate.
  - `detection_engine_management.py`: preserve the `create→get→find→patch→preview→export→import(overwrite=True)→search_alerts` sequence; only the final delete moves under the gate. `enabled` is not PATCH-editable (leave as-is).
  - `logstash_management.py`: `create_or_update` is an idempotent 204 upsert — the idempotent pre-delete is unnecessary; just namespace + gate.
  - `endpoint_management.py`, `short_urls_management.py`: teardown already guarded by an `is not None` sentinel — keep the guard, add the gate.
  - `slos_management.py`: SLO name already carries a uuid suffix (no 409) and teardown is a bulk_delete + `bulk_delete_status` poll with a single-`delete` fallback in `finally` — keep that duality, just gate it behind `should_cleanup()`. License-gated (Platinum/trial): if unlicensed, assert the real rejection rather than crashing. Instantiates `Kibana` directly (not the telemetry helper) — leave that.
- [ ] **Step 3: Compile-check the batch**

Run: `python -m py_compile examples/{alerting,apm,cases,connectors,dashboards,data_views,detection_engine,endpoint,exception_lists,logstash,saved_objects,security,short_urls,slos,visualizations,workflows}_management.py && echo ok`
Expected: `ok`
- [ ] **Step 4: Representative live run** — `python examples/cases_management.py --no-cleanup` then re-run (no 409) then `--cleanup`.
- [ ] **Step 5: Commit** `refactor(examples): keep/clean + namespacing for simple creators` (+ trailer).

#### Task C5: Dependency-ordered teardown

**Files:** `agent_builder_management.py`, `simple_saved_object.py`, `fleet_outputs_management.py`,
`fleet_policies_management.py`, `fleet_enrollment_management.py`, `synthetics_management.py`,
`spaces_management.py`, `osquery_management.py`, `entity_analytics_management.py`,
`timeline_management.py`

- [ ] **Step 1:** Apply the C3 transform, but **preserve the existing delete ordering** — teardown must respect references. From the audit:
  - `agent_builder`: delete **agent before tool** (`delete_tool(force=True)`); the conversation only exists when an LLM connector is present (see C7 for the gated branch).
  - `simple_saved_object`: delete the **visualization before the data view / index-pattern** it references.
  - `fleet_outputs`: **host → proxy → output** (host references `proxy_id`).
  - `fleet_policies`: **package policy → agent policy** (`force=True`); the side-effect `udp` package install is **not** uninstalled — document as a leak.
  - `fleet_enrollment`: **revoke enrollment key → delete policy**; the **service token has no delete API** — document as a leak.
  - `synthetics`: **monitor → private location → agent policy → global parameter**.
  - `spaces_management`: **saved objects → space** (space delete cascades to objects copied into it).
  - `osquery`: pack → saved query (delete the saved query by its `saved_object_id` from the response).
  - `entity_analytics`: keep the ordered `delete_asset_criticality …` teardown; criticality writes are upserts (safe re-run).
  - `timeline`: the **note is deleted in the happy path** (`delete_notes`) and the timeline in `finally` — keep both, both under the gate.
- [ ] **Step 2: Idempotent start** — for fixed-id resources add the own-scope pre-delete in dependency order too (e.g. delete a stale agent before a stale tool).
- [ ] **Step 3: Compile-check** the batch (`python -m py_compile examples/<each>.py`).
- [ ] **Step 4: Live run** `python examples/synthetics_management.py --no-cleanup` ×2 (no 409) then `--cleanup`; verify order via no dependency errors.
- [ ] **Step 5: Commit** `refactor(examples): keep/clean with dependency-ordered teardown` (+ trailer).

#### Task C6: Fix cleanup-inside-`try` leakers (move teardown to `finally` + gate)

**Files:** `actions_management.py`, `async_index_connector.py`, `debug_connector.py`,
`simple_space.py`, `error_handling.py`, `fleet_agents_management.py`

- [ ] **Step 1:** These currently delete on the happy path (inside `try`) or inline, so an
  exception leaks the resource. Move teardown into `finally`, gated by `should_cleanup()`, tracking
  `created` ids as they are made. Per audit:
  - `actions_management`: connectors get server ids — collect each `connector["id"]` into `created`; delete all in `finally`. The executed index connector writes ES index `kibana-connector-example` (no delete) — document.
  - `async_index_connector` (async): move the `await client.actions.delete(...)` from the happy path into `finally` (before `await client.close()`); gate it.
  - `debug_connector`: maps the **deprecated `client.actions` alias → `client.connectors`**; move the gated delete into `finally`.
  - `simple_space`: currently has no `finally` teardown — add one; gate the space delete.
  - `error_handling`: the `example_conflict_error` connector delete is function-scoped — ensure it runs in a `finally` within that function so a raised assertion still cleans up.
  - `fleet_agents`: teardown (`cancel_action`) is inline; move under a `finally` gate. Sections 1–3 are read-only.
- [ ] **Step 2: Compile-check** the batch.
- [ ] **Step 3: Live run** `python examples/simple_space.py --no-cleanup` ×2 then `--cleanup`; and the async one `python examples/async_index_connector.py --cleanup`.
- [ ] **Step 4: Commit** `fix(examples): move teardown into finally so errors don't leak resources` (+ trailer).

#### Task C7: Infra / LLM / license-gated happy paths (assert exact rejection)

**Files:** `fleet_epm_management.py`, `maintenance_windows_management.py`,
`observability_ai_assistant_management.py`, `security_ai_assistant_management.py`,
`attack_discovery_management.py`

- [ ] **Step 1:** Apply the C3 transform to the resources these DO create, **and** keep the existing
  skip/guard branches (`battle-testing-on-real-infra` three-tier). Per audit:
  - `fleet_epm`: needs Kibana→EPR internet; keep the graceful handling, namespace any installed custom integration, preserve uninstall ordering.
  - `maintenance_windows`: Platinum/Enterprise-gated; the window start is `now()+7d`. If unlicensed, assert the **exact** license-rejection message rather than skipping silently.
  - `observability_ai_assistant` / `security_ai_assistant`: LLM-connector-gated (`security_ai` on `KBNPY_LMSTUDIO_OPENAI_URL`). Those branches create + tear down their own connector — bring that under the gate; keep the "skipped (no LLM connector)" message when absent.
  - `attack_discovery`: ordered setup `space(solution="security") → .gen-ai connector(space_id) → schedule(space_id)`; tear down in reverse; keep the technical-preview guards.
- [ ] **Step 2: Compile-check** the batch.
- [ ] **Step 3: Live run** each against the local stack; where a happy path can't run, confirm it prints/asserts the real rejection (not a crash). Record the tier per file for the D1 evidence artifact.
- [ ] **Step 4: Commit** `refactor(examples): keep/clean for infra-gated examples; assert real rejections` (+ trailer).

#### Task C8: Global-state save/restore (no `should_cleanup` — always restore)

**Files:** `fleet_management.py`, `streams_management.py`, `uptime_management.py`

- [ ] **Step 1:** These mutate a **global setting** rather than creating a deletable resource, so the
  keep/clean prompt does **not** apply — they must **always restore** prior state, even on error.
  Wrap the mutate→restore in `try/finally` so the restore runs unconditionally. Per audit:
  - `fleet_management`: step 4 flips `prerelease_integrations_enabled` then restores it — there is currently **no `try/finally`** around it; add one so a mid-run error still restores.
  - `streams_management`: it probes `was_enabled` up front and only `disable()`s in `finally` if it was the one that enabled — preserve that captured-state logic; ensure it's in `finally`.
  - `uptime_management`: reads settings, applies a partial update, restores — ensure the restore is in `finally`.
- [ ] **Step 2: Compile-check** the batch.
- [ ] **Step 3: Live run** `python examples/uptime_management.py` and confirm settings are restored afterward.
- [ ] **Step 4: Commit** `fix(examples): guarantee global-state restore via finally` (+ trailer).

#### Task C9: Already-prompt examples — namespacing + idempotency pass

**Files:** `async_example.py`, `connector_management.py`, `simple_alerting_rules.py`,
`simple_index_connector.py`, `space_management.py`, `space_scoped_connector.py`,
`debug_saved_objects.py`

- [ ] **Step 1:** These already call `should_cleanup()`. Apply only: `resource_prefix(__file__)`
  namespacing of ids, idempotent pre-delete, and `print_kept(created)` on the keep branch. Per audit:
  - `connector_management` already has `create_or_find` idempotency — keep it; just namespace.
  - `simple_alerting_rules` already uses a uuid suffix — no 409 risk; namespace the prefix only.
  - `simple_index_connector`: the ES index `miconnectedindex` it writes to has no delete path — document the leak.
  - `debug_saved_objects`: a failed `create()` is silently swallowed inside `try/except: pass` around a `create_span` — narrow the except so a real create failure surfaces, then namespace.
- [ ] **Step 2: Compile-check** the batch.
- [ ] **Step 3: Live run** `python examples/simple_index_connector.py --no-cleanup` ×2 then `--cleanup`.
- [ ] **Step 4: Commit** `refactor(examples): namespace resources in already-interactive examples` (+ trailer).

#### Task C10: Read-only / debug examples — consistency check only

**Files:** `async_comprehensive.py`, `async_simple_status.py`, `basic_usage.py`,
`ml_management.py`, `simple_status.py`, `status_management.py`, `upgrade_assistant_management.py`,
`debug_spaces.py`, `debug_status.py`, `task_manager_management.py`

- [ ] **Step 1:** These create nothing (`ml.sync(simulate=True)` is a no-op demo; the rest read/list).
  No cleanup change. Only verify each still imports and runs after the C1/C2 `utils.py` changes.
- [ ] **Step 2: Compile + smoke-run**

Run: `python -m py_compile examples/{async_comprehensive,async_simple_status,basic_usage,ml_management,simple_status,status_management,upgrade_assistant_management,debug_spaces,debug_status,task_manager_management}.py && python examples/simple_status.py`
Expected: compiles; status prints.
- [ ] **Step 3: Commit** only if anything changed: `chore(examples): consistency pass on read-only examples` (+ trailer). Otherwise skip.

---

## Phase D — Live verification & release

### Task D1: Live verification across modes + evidence artifact

**Files:**
- Create: `docs/evidence/examples-0.3.1.md`

> `battle-testing-on-real-infra`: prove it live against the real stack; capture the run. Report only the subset actually run (`honest-reframing-over-overclaiming`).

- [ ] **Step 1: Ensure the stack is up**

Run: `make stack-start` (or confirm `elastic-start-local` is running) and `python examples/simple_status.py`
Expected: a healthy status response.

- [ ] **Step 2: Compile-check every example**

Run: `python -m py_compile examples/*.py && echo "all compile"`
Expected: `all compile`.

- [ ] **Step 3: Exercise a representative subset live in each mode** — pick one create-heavy sync example (e.g. `lists_management.py`), one async, and one read-only:

```bash
python examples/lists_management.py --no-cleanup      # keep; note the created ids
python examples/lists_management.py --no-cleanup      # RE-RUN: must not 409 (idempotent start)
python examples/lists_management.py --cleanup         # delete
echo "" | python examples/lists_management.py         # piped/no-TTY: must not crash, keeps
python examples/async_index_connector.py --cleanup    # async path
```
Expected: no `409`/`ConflictError`; the no-TTY run prints the keep notice and exits 0; `--cleanup` removes resources.

- [ ] **Step 4: Verify teardown reached zero** — after a `--cleanup` run, confirm no `kbnpy-<slug>-*` resources survive for that example (query the relevant list/find endpoint). Record PASS/FAIL per example.

- [ ] **Step 5: Write the evidence artifact** `docs/evidence/examples-0.3.1.md` pinning: the exact commands, Kibana version + URL, and a per-example / per-mode PASS table, plus the three-tier ranking for any infra-gated example.

- [ ] **Step 6: Commit**

```bash
git add docs/evidence/examples-0.3.1.md
git commit -m "test(examples): capture live verification evidence for 0.3.1

Evidence: docs/evidence/examples-0.3.1.md
Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task D2: Docs + version bump + release prep

**Files:**
- Modify: `examples/README.md`, `CHANGELOG.md`, `kibana/_version.py`

- [ ] **Step 1: Update `examples/README.md`** — add a short "Running examples: keep or clean" section documenting the end-of-run prompt, `--cleanup`/`--no-cleanup`, the `kbnpy-<example>-<resource>` naming, and that re-running is safe. Present-tense, matching observed behavior from D1.

- [ ] **Step 2: Add the `CHANGELOG.md` entry** under `## [Unreleased]` → new `## [0.3.1] - 2026-07-07`:

```markdown
## [0.3.1] - 2026-07-07

### Fixed
- Examples: repaired a Python-2 `except` SyntaxError in `examples/utils.py` that broke
  `import utils` (and therefore every example) under Python 3.14.

### Changed
- Examples are now human-usable end-to-end: each run prints its results, then prompts to
  keep or delete the resources it created (`--cleanup` / `--no-cleanup` override; keep is the
  default, including non-interactively). Every resource is namespaced `kbnpy-<example>-<...>`
  so kept resources never collide across examples, and setup is idempotent so re-running a
  kept example is safe.
```

- [ ] **Step 3: Bump the version**

Modify `kibana/_version.py`: `__versionstr__ = "0.3.0"` → `__versionstr__ = "0.3.1"`.

- [ ] **Step 4: Verify the version and changelog agree**

Run: `python -c "import re;print(re.search(r'\"([^\"]+)\"', open('kibana/_version.py').read()).group(1))" && grep -m1 '## \[0.3.1\]' CHANGELOG.md`
Expected: `0.3.1` and the changelog heading.

- [ ] **Step 5: Commit**

```bash
git add examples/README.md CHANGELOG.md kibana/_version.py
git commit -m "docs: document example keep/clean workflow; release 0.3.1

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 6: STOP — publishing is user-triggered.** Do not tag or push. Surface the release commit and let the maintainer run the publish workflow.
