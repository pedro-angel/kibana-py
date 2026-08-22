# shellcheck shell=sh
# Sourceable: decide whether the stack containers must trust an intercepting
# proxy's CA, and say so once.
#
# Where container egress is transparently re-terminated by a gateway presenting its
# own certificate -- a Claude Code cloud session, a corporate MITM gateway -- Kibana
# rejects every outbound HTTPS call with `self-signed certificate in certificate
# chain`. Most visibly that fails every call to the Elastic Package Registry, and so
# every `tests/integration/test_fleet_epm_*` test.
#
# This file exists because the decision was previously made in ONE of the two stack
# bring-up paths. `scripts/ci-stack-up.sh` applied the overlay;
# `local-stack.sh` -- which `make stack-start` and therefore `make test-integration`
# and the Definition-of-Done gate all use -- did not. The two paths are supposed to
# provision identically, and a stack brought up the local way had no
# `NODE_EXTRA_CA_CERTS`, so the registry tests failed there and passed in CI. One
# source, sourced by both, instead of a rule that holds in one script.
#
# Usage:
#     . "<repo>/scripts/proxy-ca.sh"
#     kibana_py_detect_proxy_ca            # sets the two variables below
#
# After the call:
#   KIBANA_PY_PROXY_CA          exported, absolute path to the CA, when one exists
#   kibana_py_proxy_ca_overlay  "docker-compose.proxy-ca.yml", or empty
#
# Applied only when the CA file is really on disk, so a GitHub runner -- where
# nothing intercepts egress -- gets an unchanged compose invocation and no behaviour
# depends on a path that does not exist there. Override the location with
# KIBANA_PY_PROXY_CA.

kibana_py_detect_proxy_ca() {
  _kibana_py_ca="${KIBANA_PY_PROXY_CA:-/root/.ccr/ca-bundle.crt}"
  if [ -f "$_kibana_py_ca" ]; then
    KIBANA_PY_PROXY_CA="$_kibana_py_ca"
    export KIBANA_PY_PROXY_CA
    kibana_py_proxy_ca_overlay="docker-compose.proxy-ca.yml"
  else
    kibana_py_proxy_ca_overlay=""
  fi
  unset _kibana_py_ca
}
