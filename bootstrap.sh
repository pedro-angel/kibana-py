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
