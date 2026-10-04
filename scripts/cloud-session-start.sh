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
# does not exist. Without it every `make` leaf that runs a tool ($(VENV_BIN)/...) fails.
# Synchronous on purpose: it costs about a minute of session start, and it guarantees
# nothing in the session runs before its tools exist.
#
# The same Docker start logic lives in scripts/cloud-setup.sh. The duplication is
# forced: that script is fetched standalone by the environment's bootstrap, before the
# repository exists on disk, so it cannot source anything from here.
#
# Local sessions exit at the first line. CLAUDE_CODE_REMOTE is "true" only inside a
# cloud session VM.

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# The repository is wherever this script lives -- not $CLAUDE_PROJECT_DIR, which in a
# session started one level up names the parent directory.
cd "$(dirname "$0")/.." || exit 0

start_docker() {
  if docker info >/dev/null 2>&1; then
    echo "[cloud-session-start] docker daemon already running"
    return 0
  fi

  # The snapshot also carries the setup run's /var/run/docker.pid. Its PID is
  # meaningless on a freshly booted VM, but low PIDs are reused early in boot, so
  # dockerd can find an unrelated live process behind it and refuse to start
  # ("process with PID 567 is still running"). No dockerd is running here -- docker
  # info just failed -- so a pidfile is stale by definition.
  if ! pgrep -x dockerd >/dev/null 2>&1; then
    rm -f /var/run/docker.pid
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
  # A fresh clone has no .venv; a resumed session may already have one.
  if [ -x .venv/bin/python ]; then
    echo "[cloud-session-start] dev environment already present (.venv)"
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
