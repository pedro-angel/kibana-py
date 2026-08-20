#!/usr/bin/env bash
# cloud-setup.sh -- setup script for the kibana-py Claude Code cloud environment.
#
# Runs as root on the session VM (Ubuntu 24.04, x86_64) BEFORE Claude Code starts,
# once per environment-cache generation. Anthropic snapshots the filesystem after it
# exits, so whatever this script leaves on disk -- apt packages, pulled Docker images
# -- is already there for every later session. Running processes are NOT snapshotted:
# the stack itself is brought up per session with ./scripts/ci-stack-up.sh.
#
# Wire it up by pasting this bootstrap into the environment's "Setup script" field
# (full walkthrough: docs/source/development/cloud-environment.md):
#
#   #!/bin/bash
#   curl -fsSL https://raw.githubusercontent.com/pedro-angel/kibana-py/main/scripts/cloud-setup.sh \
#     -o /tmp/cloud-setup.sh && bash /tmp/cloud-setup.sh
#
# Two constraints the platform imposes, and how this script answers them:
#   * It must exit 0 -- a non-zero exit fails session start. Every step is fail-open;
#     a step that cannot run logs why and is skipped.
#   * It must finish in roughly five minutes -- overrunning means no cache is built,
#     so every session pays the full pull. Pulls run against a wall-clock deadline and
#     stop when it expires; completed layers still cache, and anything missed is
#     pulled on demand inside the session.
#
# Environment variables (set them in the cloud environment's variables field):
#   KIBANA_PY_STACK_VERSIONS  space-separated stack versions to pre-pull, most
#                             important first -- the leftmost gets the budget.
#                             Default: "9.5.1 9.4.3".
#   KIBANA_PY_PULL_BUDGET     seconds allowed for all image pulls. Default: 210.

set -uo pipefail   # deliberately not -e: a failed step must not fail session start

# This script's stdout is not retrievable from inside a later session, and the whole
# point of the budget is a claim about how long it took. Tee to a file so the snapshot
# carries the run's own record: a session can read it and report measured timings
# instead of asserting them.
log_file=/var/log/kibana-py-cloud-setup.log
touch "$log_file" 2>/dev/null || log_file=/tmp/kibana-py-cloud-setup.log
exec > >(tee -a "$log_file") 2>&1

versions="${KIBANA_PY_STACK_VERSIONS:-9.5.1 9.4.3}"
budget="${KIBANA_PY_PULL_BUDGET:-210}"
registry="docker.elastic.co"
images="elasticsearch/elasticsearch kibana/kibana apm/apm-server"

log() { printf '[cloud-setup] %s\n' "$*"; }

# --- gh: not on the session image; the built-in GitHub tools cover PRs, but
# --- `gh api`, `gh release` and `gh workflow run` are how this repo is maintained.
log "installing gh"
DEBIAN_FRONTEND=noninteractive apt-get update -qq >/dev/null 2>&1 \
  || log "apt-get update failed -- continuing without it"
if DEBIAN_FRONTEND=noninteractive apt-get install -y -qq gh >/dev/null 2>&1; then
  log "gh $(gh --version 2>/dev/null | head -1 | awk '{print $3}') installed"
else
  log "gh install failed -- built-in GitHub tools still work"
fi

# --- Docker: required for the Elastic stack. Fail open, but never silently: the first
# --- run of this script found no daemon and discarded the reason, which made the
# --- difference between a wrong start command and an environment that cannot run
# --- nested containers unknowable from inside a later session.
dockerd_log=/var/log/kibana-py-dockerd.log
touch "$dockerd_log" 2>/dev/null || dockerd_log=/tmp/kibana-py-dockerd.log

wait_for_daemon() {
  for _ in $(seq 1 "$1"); do
    docker info >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}

if ! docker info >/dev/null 2>&1; then
  # PID 1 on the session VM is a Firecracker init shim, not systemd, so `service
  # docker start` is a silent no-op and waiting on it only burns pull budget. Try it
  # only where an init system actually exists; otherwise launch the daemon directly.
  if [ -d /run/systemd/system ]; then
    log "docker daemon not responding -- trying the service wrapper"
    service docker start 2>&1 | sed 's/^/[cloud-setup]   service: /' || true
    wait_for_daemon 10 || true
  fi
fi
if ! docker info >/dev/null 2>&1; then
  log "launching dockerd directly"
  nohup dockerd >>"$dockerd_log" 2>&1 &
  wait_for_daemon 20 || true
fi
if ! docker info >/dev/null 2>&1; then
  log "docker unavailable at setup time -- skipping the image pre-pull"
  log "dockerd's own last words follow. A permissions or cgroup error means this"
  log "environment class cannot run nested containers and no script can fix it;"
  log "anything else is a start problem that can be fixed:"
  tail -n 20 "$dockerd_log" 2>/dev/null | sed 's/^/[cloud-setup]   dockerd: /'
  [ -s "$dockerd_log" ] || log "  dockerd wrote nothing -- it never started"
  exit 0
fi
log "docker daemon up (server $(docker version --format '{{.Server.Version}}' 2>/dev/null))"

# --- Pre-pull the stack images so the snapshot carries them.
# Elastic images come from docker.elastic.co, which is NOT on the Trusted default
# allowlist. The environment must use Custom network access covering *.elastic.co --
# note the wildcard: naming docker.elastic.co alone still fails every pull, because
# the registry's 401 challenge sends the client to docker-auth.elastic.co for a token
# and the proxy refuses the CONNECT to that separate host.
deadline=$(( SECONDS + budget ))
pulled=0
missed=0

for version in $versions; do
  remaining=$(( deadline - SECONDS ))
  if [ "$remaining" -le 15 ]; then
    log "budget of ${budget}s exhausted before ${version} -- skipping it"
    missed=$(( missed + 3 ))
    continue
  fi
  log "pulling ${version} images in parallel (${remaining}s of budget left)"
  pids=""
  for image in $images; do
    timeout "$remaining" docker pull --quiet "${registry}/${image}:${version}" >/dev/null 2>&1 &
    pids="${pids} $!"
  done
  for pid in $pids; do
    if wait "$pid"; then
      pulled=$(( pulled + 1 ))
    else
      missed=$(( missed + 1 ))
    fi
  done
done

log "cached ${pulled} image(s); ${missed} left to pull on demand"
docker images --format '{{.Repository}}:{{.Tag}} ({{.Size}})' 2>/dev/null \
  | grep "^${registry}" | sed 's/^/[cloud-setup]   /' || true
log "finished in ${SECONDS}s (this transcript: ${log_file})"

exit 0
