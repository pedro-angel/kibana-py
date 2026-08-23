#!/usr/bin/env bash
# cloud-session-start.sh -- SessionStart hook, cloud sessions only.
#
# Brings a fresh session VM up to "can actually work on this repository": a running
# Docker daemon, and the dev environment `make setup` builds.
#
# Docker: the environment cache is a filesystem snapshot: it carries the images that
# scripts/cloud-setup.sh pulled, but not the daemon that pulled them. Every session
# therefore starts with dockerd absent, and PID 1 on the session VM is a Firecracker
# init shim rather than systemd -- there is no service manager to start it. Without
# this hook, ./scripts/ci-stack-up.sh fails in every session after the first.
#
# The dev environment: .venv lives inside the repository, and the repository is cloned
# fresh for every session, so no snapshot can carry it -- it has to be built here or it
# does not exist. Without it every `make` leaf that runs a tool ($(VENV_BIN)/...) fails,
# and an agent working in the session has no black, no ruff, no pytest: it can only
# approximate the gates with substitutes, which is how unformatted code reaches a
# maintainer's `make dod` and costs them a run.
#
# Synchronous on purpose. It costs about a minute of session start, and it buys the
# guarantee that nothing in the session runs before its tools exist. Switching to async
# (print {"async": true, "asyncTimeout": 300000} first) would start the session sooner
# at the price of a race with whatever runs first.
#
# The same start logic lives in scripts/cloud-setup.sh. The duplication is forced:
# that script is fetched standalone by the environment's bootstrap, before the
# repository exists on disk, so it cannot source anything from here.
#
# Local sessions exit at the first line. CLAUDE_CODE_REMOTE is "true" only inside a
# cloud session VM.

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}" || exit 0

start_docker() {
  if docker info >/dev/null 2>&1; then
    echo "[cloud-session-start] docker daemon already running"
    return 0
  fi

  local log=/var/log/kibana-py-dockerd.log
  touch "$log" 2>/dev/null || log=/tmp/kibana-py-dockerd.log
  nohup dockerd >>"$log" 2>&1 &

  for _ in $(seq 1 20); do
    if docker info >/dev/null 2>&1; then
      echo "[cloud-session-start] started dockerd (server $(docker version --format '{{.Server.Version}}' 2>/dev/null))"
      return 0
    fi
    sleep 1
  done

  # Never fail the session over this: report it and let the stack commands surface it.
  echo "[cloud-session-start] dockerd did not come up; see $log"
}

start_dev_environment() {
  # Idempotent: `make setup` runs only when there is no virtualenv, or when the one
  # there predates the current pyproject.toml. environment-current.py is the same
  # check the Definition-of-Done gate preflights with, so "current" means one thing.
  if [ -x .venv/bin/python ] &&
     .venv/bin/python scripts/checks/environment-current.py \
       --python .venv/bin/python >/dev/null 2>&1; then
    echo "[cloud-session-start] dev environment already current"
    return 0
  fi

  local log=/var/log/kibana-py-setup.log
  touch "$log" 2>/dev/null || log=/tmp/kibana-py-setup.log
  echo "[cloud-session-start] building the dev environment (make setup) -- about a minute"
  if make setup >>"$log" 2>&1; then
    echo "[cloud-session-start] dev environment ready (.venv)"
  else
    # Same rule as dockerd: report, never fail the session.
    echo "[cloud-session-start] make setup failed; see $log -- run 'make setup' by hand"
  fi
}

start_docker
start_dev_environment
exit 0
