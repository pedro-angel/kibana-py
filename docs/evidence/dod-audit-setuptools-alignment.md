# Evidence — collapse the base-tool upgrade to one source so a fresh-clone audit is clean

**Date:** 2026-07-16 (point-in-time; see *Caveats*)
**Change under test:**
- New `scripts/upgrade-base-build-tools.sh` — runs `"$PYTHON" -m pip install --upgrade pip setuptools`.
- `Makefile` `setup` calls it with the venv python; `.github/workflows/test.yml`'s install
  step calls it with the system python. One definition, consumed by both — the same
  single-source pattern the repo already uses for `scripts/ci-stack-up.sh`.
**Base commit:** `b1905c0` (branch `ci/align-make-setup-setuptools-audit`).

## Why

`make dod`'s `audit_clean` runs `make audit` → bare `pip-audit`, which scans the whole
venv. On a **fresh** venv, `make setup` upgraded only `pip`, so Python 3.11's bundled
`setuptools 79.0.1` (advisory `PYSEC-2026-3447`, fixed in `83.0.0`) remained and pip-audit
flagged it — a NO-GO. CI's install step already upgraded `setuptools` (commit `1dbd81c`),
so CI was green while the local gate was red.

The first cut of this fix simply added `setuptools` to the Makefile's install line. An
adversarial review correctly flagged that as **not** a de-drift: it made the Makefile line
*match* an independent hand-typed CI line, coupled only by a "keep in sync" comment — the
exact anti-pattern `configuration-single-source-of-truth` names (duplicate a value in two
files with no guard). This version instead **collapses both call sites onto one script**,
so there is nothing to keep in sync.

## Run (properties, not runner)

| Property | Value |
|---|---|
| Arch / OS | arm64 / Darwin |
| Python | 3.11.15 (release floor; the version that bundles the flagged setuptools) |
| pip / pip-audit | pip 26.1.2 / pip-audit 2.10.1 |
| Role | local arm64 developer host |

> The interpreter must be on PATH. On this host `python3.11` is not a PATH name; the runs
> used the pyenv 3.11.15 interpreter explicitly (`make setup PYTHON=<abs path to 3.11>`).

## Test A — the script clears the advisory (isolated)

Fresh 3.11 venv (pyenv 3.11.15), old-style install (pip only, `pip-audit==2.10.1`), then the
shared script. Captured verbatim (venv path redacted for identity hygiene):

```
# BEFORE — old-style (pip upgraded, setuptools NOT)
$ pip show setuptools | grep ^Version
Version: 79.0.1
$ pip-audit ; echo exit=$?
Found 1 known vulnerability in 1 package
Name       Version ID              Fix Versions
setuptools 79.0.1  PYSEC-2026-3447 83.0.0
exit=1

# run the shared script (PYTHON=<venv>/bin/python — the mechanism the Makefile uses)
$ PYTHON=<venv>/bin/python ./scripts/upgrade-base-build-tools.sh ; echo exit=$?
exit=0

# AFTER
$ pip show setuptools | grep ^Version
Version: 83.0.0
$ pip-audit ; echo exit=$?
No known vulnerabilities found
exit=0
```

→ RED reproduced (`exit=1`, `PYSEC-2026-3447`) → shared script → fully clean (`exit=0`,
"No known vulnerabilities found"). The `PYTHON=` override works. **PASS.**

## Test B — end-to-end through the real Makefile (fresh clone)

```
make clean-all                 # removes .venv → simulates a fresh clone
make setup PYTHON=<3.11>       # setup now calls ./scripts/upgrade-base-build-tools.sh
make audit                     # == the DoD gate's audit_clean criterion
```

Captured (`make setup PYTHON=<pyenv 3.11.15>`; absolute interpreter path redacted for identity hygiene):

```
$ make setup PYTHON=<pyenv 3.11.15> ; echo exit=$?
✓ Dev environment ready. Activate with: source .venv/bin/activate
✓ Pre-commit hooks installed (pre-commit + pre-push).
exit=0
$ .venv/bin/pip show setuptools | grep ^Version
Version: 83.0.0
$ make audit ; echo exit=$?
.venv/bin/pip-audit
No known vulnerabilities found
exit=0
```

→ A fresh clone passes `audit_clean` with **no manual setuptools remediation** (the manual
step the 0.4.2 release needed). Only prerequisite: a supported interpreter on PATH or passed
via `PYTHON=` — here pyenv 3.11.15. **PASS.**

## Scope & caveats

- **Reused / pre-fix venv is not auto-healed.** `make audit` and `make dod` run against
  whatever `.venv` exists; they do not depend on `make setup`. A developer with a *pre-fix*
  3.11 venv (setuptools 79.0.1) still NO-GOs until they re-run `make setup` or `make clean-all`.
  The fix targets fresh setups; in-place remediation is `make setup` (or `pip install -U 'setuptools>=83'`).
- **On 3.12+ the upgrade installs a setuptools that wasn't there.** Fresh 3.12/3.13/3.14 venvs
  bundle no setuptools, and `.[dev,all]` doesn't need it at runtime; the upgrade installs a
  *current* (clean) setuptools on those interpreters. This matches CI's behavior exactly and
  keeps the audited env uniform; it is not a runtime dependency and is not in the wheel.
- **Unbounded (latest), by design.** No floor/ceiling pin — self-healing against future
  setuptools advisories rather than chasing versions (the deliberate choice in `1dbd81c`).
  Trade-off acknowledged: a future setuptools regression could break the dev install; that is
  accepted here to stay identical to CI. Ordering: setuptools is upgraded *before*
  `pip install -e ".[dev,all]"`; verified today nothing in the resolved tree constrains
  setuptools (`pip show setuptools` → `Required-by:` empty), so the editable install does not
  downgrade it.
- **Point-in-time result.** `pip-audit` queries a live advisory DB and the upgrade fetches the
  current latest; the GREEN above is valid as of 2026-07-16. Self-healing bounds, but does not
  eliminate, future audit changes.
- **User impact: none.** `setuptools` is a build tool, not in the published wheel; the `0.4.2`
  release and CI were already green. Only the local DoD gate on a fresh venv was red (observed
  during the 0.4.2 release, which needed a manual `setuptools` upgrade to reach `VERDICT: GO`).
