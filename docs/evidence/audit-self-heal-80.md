# Evidence — `make audit` self-heals base build tools on an existing venv (#80)

**Date:** 2026-08-01
**Change under test:** `Makefile` `audit` leaf now runs `scripts/upgrade-base-build-tools.sh`
(the single source PR #67 established, also called by `make setup` and CI's install step)
before `pip-audit`, using the same `PYTHON=$(VENV_BIN)/python` threading `make setup` uses.
**Base commit:** `91a12fa` (branch `fix/audit-self-heal-80`).

## Why

PR #67 collapsed the pip+setuptools upgrade to one script and wired it into `make setup` and
CI's per-job install step, fixing the **fresh-venv** case. It explicitly left a gap, recorded
in its own evidence doc (`docs/evidence/dod-audit-setuptools-alignment.md`, *Scope & caveats*):
`make audit` / `make dod` run against whatever `.venv` already exists — they don't depend on
`make setup` — so a long-lived venv is never re-healed. The 2026-07-31 adversarial deep review
(release-hygiene lens) flagged that residual as issue #80: the next setuptools advisory
reproduces the exact 0.4.2 incident (CI green, local DoD NO-GO) on any developer's existing
venv, not just a fresh one.

Fix: the `audit` leaf itself calls the shared script before `pip-audit`, so `make audit`
(and therefore the DoD gate's `audit_clean` criterion, which delegates to it) self-heals
every run — no dependency on when `make setup` was last run. Threading (`PYTHON=$(VENV_BIN)/python`)
is copied verbatim from the `setup` target so there is exactly one call pattern, not a second
hand-synced one.

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / Darwin |
| Python | 3.11.15 (release floor; the version that bundles the flagged setuptools) |
| pip-audit | 2.10.1 (both the real dev venv and the throwaway venv below) |
| Role | local arm64 developer host |

Per the task's isolation requirement, the RED/heal battle test ran against a **throwaway venv
copy** (`python3.11 -m venv` into a scratch directory, outside the repo), never against the
real `.venv` the working tree depends on. The real `.venv` was only ever driven forward by its
own already-healthy `make audit` run (see *Test C*), never downgraded.

## Test A — RED: current (pre-fix) `make audit` fails on a downgraded venv

Throwaway venv, setuptools force-downgraded to `79.0.1` (below the `PYSEC-2026-3447` fix,
`83.0.0`), `pip-audit` installed but the shared upgrade script not yet wired into `audit`.
Captured verbatim (throwaway venv path redacted for identity hygiene):

```
$ <throwaway>/bin/pip show setuptools | grep -i version
Version: 79.0.1
$ make audit VENV_DIR=<throwaway> ; echo exit=$?
<throwaway>/bin/pip-audit
Found 8 known vulnerabilities in 2 packages
Name       Version ID              Fix Versions
---------- ------- --------------- ------------
pip        24.0    PYSEC-2026-196  26.1.2
pip        24.0    PYSEC-2026-1795 25.3
pip        24.0    PYSEC-2026-1796 26.0
pip        24.0    PYSEC-2026-196  26.1.2
pip        24.0    PYSEC-2026-2875 26.1
pip        24.0    PYSEC-2026-2876 26.1
setuptools 79.0.1  PYSEC-2026-3447 83.0.0
setuptools 79.0.1  PYSEC-2026-3447 83.0.0
make: *** [audit] Error 1
exit=2
```

→ RED reproduced: `make audit` fails (`pip-audit` flags `PYSEC-2026-3447`, plus the venv's
untouched default pip). This is the 0.4.2 symptom, now reproduced through `make audit` itself
rather than bare `pip-audit`, on a venv the fix has not yet touched. **Confirms the bug.**

## Test B — HEAL: fixed `make audit` self-heals the same venv and passes

Same throwaway venv (still at `setuptools 79.0.1` — untouched between Test A and B), now
against the fixed Makefile:

```
$ make audit VENV_DIR=<throwaway> ; echo exit=$?
PYTHON=<throwaway>/bin/python ./scripts/upgrade-base-build-tools.sh
Requirement already satisfied: pip in <throwaway>/lib/python3.11/site-packages (24.0)
Collecting pip
  Using cached pip-26.2-py3-none-any.whl.metadata (4.6 kB)
Requirement already satisfied: setuptools in <throwaway>/lib/python3.11/site-packages (79.0.1)
Collecting setuptools
  Using cached setuptools-83.0.0-py3-none-any.whl.metadata (6.6 kB)
Using cached pip-26.2-py3-none-any.whl (1.8 MB)
Using cached setuptools-83.0.0-py3-none-any.whl (1.0 MB)
Installing collected packages: setuptools, pip
  Attempting uninstall: setuptools
    Found existing installation: setuptools 79.0.1
    Uninstalling setuptools-79.0.1:
      Successfully uninstalled setuptools-79.0.1
  Attempting uninstall: pip
    Found existing installation: pip 24.0
    Uninstalling pip-24.0:
      Successfully uninstalled pip-24.0
Successfully installed pip-26.2 setuptools-83.0.0
<throwaway>/bin/pip-audit
No known vulnerabilities found
exit=0
$ <throwaway>/bin/pip show setuptools | grep -i version
Version: 83.0.0
```

→ The upgrade command line and pip's own install output are printed by `make` (no `@` prefix,
matching the `setup` target's existing convention) — the self-heal is **observable, not
silent**. `pip-audit` then reports clean. **PASS.**

## Test C — fresh/healthy-venv path unaffected

Real repo `.venv` (never downgraded; `setuptools` already `83.0.0`), fixed Makefile:

```
$ .venv/bin/pip show setuptools pip | grep -E '^(Name|Version)'
Name: setuptools
Version: 83.0.0
Name: pip
Version: 26.1.2
$ make audit ; echo exit=$?
PYTHON=.venv/bin/python ./scripts/upgrade-base-build-tools.sh
Requirement already satisfied: pip in ./.venv/lib/python3.11/site-packages (26.1.2)
Collecting pip
  Using cached pip-26.2-py3-none-any.whl.metadata (4.6 kB)
Requirement already satisfied: setuptools in ./.venv/lib/python3.11/site-packages (83.0.0)
Using cached pip-26.2-py3-none-any.whl (1.8 MB)
Installing collected packages: pip
  Attempting uninstall: pip
    Found existing installation: pip 26.1.2
    Uninstalling pip-26.1.2:
      Successfully uninstalled pip-26.1.2
Successfully installed pip-26.2
.venv/bin/pip-audit
No known vulnerabilities found
exit=0
```

→ A venv that's already fixed just picks up the ambient `pip` point release (harmless,
setuptools was already satisfied) and stays green — no regression on the common case. **PASS.**
The real `.venv` was never downgraded during this work, so no restoration step was needed for
it.

## Test D — DoD gate's `audit_clean` criterion end-to-end (downgraded-then-healed venv)

Requirement: prove the *gate*, not just the make leaf, stops reproducing the incident — without
running the full (integration/benchmark/matrix-inclusive) `make dod`. A throwaway single-
criterion `dod.config` (`audit_clean = required`, everything else `n/a`) drives the real
`scripts/checks/definition-of-done.sh` against the same throwaway venv, selected via the
`VENV_DIR` env var the Makefile already respects (`VENV_DIR ?= .venv`).

**D1 — gate-level RED** (Makefile temporarily reverted via `git stash` to the pre-fix `audit`
leaf; throwaway venv re-downgraded to `setuptools 79.0.1`):

```
$ VENV_DIR=<throwaway> scripts/checks/definition-of-done.sh <tmp>/dod-audit-only.config
Definition-of-Done gate (<tmp>/dod-audit-only.config)
  NO-GO audit_clean  (log: /tmp/dod-kibana-py/audit_clean.log)
VERDICT: NO-GO (fix the criteria above, or mark them n/a in <tmp>/dod-audit-only.config as a visible decision)
$ echo exit=$?
exit=1
```

(log tail: `pip-audit` → `Found 2 known vulnerabilities in 1 package` / `setuptools 79.0.1
PYSEC-2026-3447` / `make: *** [audit] Error 1`)

**D2 — gate-level GO** (`git stash pop` restores the fix; same still-downgraded throwaway
venv, no manual remediation in between):

```
$ VENV_DIR=<throwaway> scripts/checks/definition-of-done.sh <tmp>/dod-audit-only.config
Definition-of-Done gate (<tmp>/dod-audit-only.config)
  GO    audit_clean
VERDICT: GO
$ echo exit=$?
exit=0
```

(log shows the upgrade script running — `Successfully installed setuptools-83.0.0` — then
`pip-audit` → `No known vulnerabilities found`.)

→ The gate-level symptom (NO-GO on a stale venv the gate itself doesn't heal) is gone: the
same downgraded venv goes from `VERDICT: NO-GO` to `VERDICT: GO` through the unmodified
`scripts/checks/definition-of-done.sh`, with no step in between other than the Makefile fix
itself. Per the task's scope, the full integration-tier `make dod` (unit/integration/
benchmark/matrix) was **not** run here — that is the campaign's final gate, not this fix's
battle test.

## CI alignment

`.github/workflows/test.yml`'s `unit-lint-type` job does **not** call `make audit` (or `make
dod`) at all — it calls `pip-audit` directly as its own step, after an "Install dependencies"
step that already runs `./scripts/upgrade-base-build-tools.sh` once for the whole job (system
Python, before `pip install -e ".[dev,all]"`, `mypy`, `bandit`, and `pytest` too — not just
before the audit step). Confirmed via `grep -rn "make audit\|make dod" .github/workflows/`:
no hits. So this fix does **not** introduce a double-upgrade in CI — the Makefile `audit` leaf
and CI's install-step call are two independent call sites that were already both derived from
the single shared script (`scripts/upgrade-base-build-tools.sh`); CI simply never routes
through the Makefile leaf.

**Decision: keep CI's explicit step, unchanged.** It isn't a hand-synced duplicate of the
`audit` leaf's logic (both call the same script, so there's nothing to keep in sync) and it
does more than the leaf needs: CI's job also runs `mypy`/`bandit`/`pytest` in the *same*
environment after the upgrade, so the upgrade has to happen once, early, for the whole job —
not scoped to only the audit step. Moving CI onto `make audit` would couple an unrelated step
ordering decision to this fix and buys nothing, since the single-source property (one script,
two callers) already holds without it.

## Scope & caveats

- **Build-tool-only change.** `setuptools`/`pip` are not in the published wheel; no `pip
  install kibana-py` user is affected.
- **Unbounded (latest) upgrade**, matching the existing script's documented self-healing
  design (`scripts/upgrade-base-build-tools.sh` header) — not re-litigated here.
- **Point-in-time result.** `pip-audit` queries a live advisory DB; the GREEN results above are
  valid as of 2026-08-01.
- **Throwaway venv, not the real one.** The RED/heal/gate battle test (Tests A, B, D) ran
  entirely against a scratch venv created for this task and discarded afterward; the repo's
  real `.venv` was touched only by its own legitimate, already-green `make audit` run (Test C),
  which left it healthy (and, incidentally, bumped its `pip` to the current point release —
  expected self-heal behavior, not a side effect of the experiment).
