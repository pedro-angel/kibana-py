#!/usr/bin/env bash
# cloud-session-start.sh -- SessionStart hook, cloud sessions only.
#
# The environment cache is a filesystem snapshot: it carries the images that
# scripts/cloud-setup.sh pulled, but not the daemon that pulled them. Every session
# therefore starts with dockerd absent, and PID 1 on the session VM is a Firecracker
# init shim rather than systemd -- there is no service manager to start it. Without
# this hook, ./scripts/ci-stack-up.sh fails in every session after the first.
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

if docker info >/dev/null 2>&1; then
  echo "[cloud-session-start] docker daemon already running"
  exit 0
fi

log=/var/log/kibana-py-dockerd.log
touch "$log" 2>/dev/null || log=/tmp/kibana-py-dockerd.log
nohup dockerd >>"$log" 2>&1 &

for _ in $(seq 1 20); do
  if docker info >/dev/null 2>&1; then
    echo "[cloud-session-start] started dockerd (server $(docker version --format '{{.Server.Version}}' 2>/dev/null))"
    exit 0
  fi
  sleep 1
done

# Never fail the session over this: report it and let the stack commands surface it.
echo "[cloud-session-start] dockerd did not come up; see $log"
exit 0
