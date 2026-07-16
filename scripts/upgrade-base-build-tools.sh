#!/usr/bin/env bash
# Upgrade the base build tools (pip + setuptools) in the target environment.
# Single source of truth for the base-tool upgrade: called by BOTH the Makefile
# `setup` target (venv python) and the CI install step (.github/workflows/test.yml,
# system python), so the two can't drift.
#
# Why setuptools: pip-audit (the `make audit` / DoD `audit_clean` gate, and CI's
# "Security audit dependencies" step) scans the WHOLE environment, and older
# Pythons (3.11) ship a setuptools that trails security fixes
# (e.g. 79.0.1 / PYSEC-2026-3447, fixed in 83.0.0). Upgrading to the latest is
# self-healing — no version pinned to chase advisory-by-advisory. Newer Pythons
# bundle no setuptools; this installs a current one, which pip-audit also accepts.
#
# PYTHON selects the interpreter whose `-m pip` is used: the venv python locally,
# the system python in CI. Defaults to `python`. The script's own logic is
# cwd-independent; both callers run it from the repo root (and the Makefile passes
# a repo-root-relative interpreter path, so run it from the repo root).
set -euo pipefail

PYTHON="${PYTHON:-python}"
"$PYTHON" -m pip install --upgrade pip setuptools
