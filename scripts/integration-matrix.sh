#!/usr/bin/env bash
# Run the release-gate integration selection against EVERY supported Kibana version.
#
# The release gate (.github/workflows/release.yml) matrixes over the supported set,
# building that matrix from `scripts/checks/supported-versions.py --matrix`. Locally
# the same coverage was a manual loop -- export ES_LOCAL_VERSION, provision, run the
# suite, tear down, repeat -- with nothing to catch a line the runner forgot. At two
# supported lines that is a nuisance; at four it is a defect waiting to happen, and
# it makes the local gate WEAKER than the CI gate it is supposed to be a superset of.
# This script is that loop, driven by the same single source, so adding a line to
# kibana/_compat.py adds it here with no edit anywhere.
#
# Per version: destroy the stack and its volumes, provision at that pin through
# scripts/ci-stack-up.sh, then run `make test-integration-ci` -- the release gate's
# own leaf, so the pytest command string still lives in the Makefile recipe exactly
# once. Volumes are destroyed between versions so no index, saved object or stream
# survives from one line into the next (the method the 9.4.5/9.5.2 battle test used:
# docs/evidence/multi-version-9.4.5-9.5.2.md).
#
# Versions run OLDEST FIRST, and the last stack is left running. Both are about the
# state this leaves the machine in, and neither is cosmetic:
#   - ci-stack-up.sh writes ES_LOCAL_VERSION into elastic-start-local/.env on every
#     bring-up, and local-stack.sh only re-seeds that file when it is MISSING. Ending
#     on the newest pin therefore leaves .env agreeing with the template, instead of
#     silently pinning every later `make stack-start` to the oldest supported line.
#   - `make test-benchmark` (the DoD criterion that runs right after this one) depends
#     on stack-start and used to inherit the warm stack `make test-integration` left
#     up. Tearing down at the end would have made it rebuild a stack from scratch.
#
# Fails closed. A failing version does not abort the run -- the remaining versions
# still tell you something -- but the exit status is non-zero and the summary names
# it. An empty or unreadable supported set is a hard error, never a silent pass.
#
# Locally the api-key auth tests need ES_LOCAL_API_KEY exported (ci-stack-up.sh mints
# one only under GitHub Actions); without it they skip, which the gate allows.
#
# Usage:  make test-integration-matrix     (or: ./scripts/integration-matrix.sh)

set -uo pipefail   # deliberately not -e: a failing version is recorded, not fatal

# A MAKEFLAGS leaked from a parent make (-i, -k, a -j jobserver) would make the
# child `make test-integration-ci` ignore recipe errors and report a false pass.
# The DoD gate clears these for the same demonstrated reason.
unset MAKEFLAGS MFLAGS

here="$(cd "$(dirname "$0")/.." && pwd)"
cd "$here" || exit 2

logdir="${TMPDIR:-/tmp}/kibana-py-integration-matrix"
mkdir -p "$logdir"

# --- the supported set, from the one place it is declared -------------------
if ! matrix_json="$(python3 scripts/checks/supported-versions.py --matrix)"; then
  echo "FAIL: could not read the supported set from kibana/_compat.py" >&2
  exit 2
fi
if ! versions="$(printf '%s' "$matrix_json" |
    python3 -c 'import json,sys; print(" ".join(json.load(sys.stdin)))')"; then
  echo "FAIL: the supported set is not the JSON array this script expects: $matrix_json" >&2
  exit 2
fi
case "$versions" in
  *[!\ ]*) : ;;
  *) echo "FAIL: the supported set is empty -- refusing to report a green matrix over zero versions" >&2
     exit 2 ;;
esac

# --- preflight: the gate's own pytest flags need the [probe] extra ----------
# `make setup` installs .[dev,all]; pytest-timeout rides along via dev's [probe],
# but a venv created before that change has no --timeout and every version would
# fail identically on an argument error. Say so once, up front.
pytest_bin="${PYTEST:-$here/.venv/bin/pytest}"
probe_python="$(dirname "$pytest_bin")/python"
if [ -x "$probe_python" ] && ! "$probe_python" -c 'import pytest_timeout' >/dev/null 2>&1; then
  echo "FAIL: pytest-timeout is missing, so 'make test-integration-ci' cannot run." >&2
  echo "      Re-run 'make setup' (dev now pulls the [probe] extra), or install it into $(dirname "$pytest_bin")." >&2
  exit 2
fi

# Oldest first (the declared set is newest-first) -- see the header for why the run
# has to END on the newest pin.
ordered=""
for version in $versions; do
  ordered="$version${ordered:+ }$ordered"
done

echo "Integration matrix over the supported set, oldest first: $ordered"
echo "Logs: $logdir"

# --- the loop ---------------------------------------------------------------
results=""
nogo=0
total_passed=0
total_skipped=0
total_failed=0

for version in $ordered; do
  log="$logdir/$version.log"
  echo
  echo "======================================================================"
  echo "  Kibana $version"
  echo "======================================================================"

  # Fresh stack per version: no state from the previous line survives.
  make stack-destroy >>"$log" 2>&1 || true   # nothing to destroy on the first pass

  if ! ES_LOCAL_VERSION="$version" ./scripts/ci-stack-up.sh 2>&1 | tee -a "$log"; then
    echo "  NO-GO $version  (stack never came up; log: $log)"
    results="$results
  NO-GO $version  stack bring-up failed (log: $log)"
    nogo=1
    continue
  fi

  if make test-integration-ci 2>&1 | tee -a "$log"; then
    status=GO
  else
    status=NO-GO
    nogo=1
  fi

  summary="$(grep -E '[0-9]+ (passed|skipped|failed|error)|no tests ran' "$log" | tail -1)"
  passed="$(printf '%s\n' "$summary" | sed -n 's/ passed.*//p' | sed 's/.*[^0-9]//')"
  skipped="$(printf '%s\n' "$summary" | sed -n 's/ skipped.*//p' | sed 's/.*[^0-9]//')"
  failed="$(printf '%s\n' "$summary" | sed -n 's/ failed.*//p' | sed 's/.*[^0-9]//')"
  passed=${passed:-0}; skipped=${skipped:-0}; failed=${failed:-0}

  # Exit 0 on zero executed tests is a false green -- pytest exits 0 on an empty
  # or fully-deselected run. Same guard the DoD gate applies per suite.
  if [ "$status" = GO ] && [ "$passed" -lt 1 ]; then
    status=NO-GO
    nogo=1
    results="$results
  NO-GO $version  exit 0 but 0 tests passed (log: $log)"
  else
    results="$results
  $status $version  ($passed passed, $skipped skipped, $failed failed)"
  fi

  total_passed=$(( total_passed + passed ))
  total_skipped=$(( total_skipped + skipped ))
  total_failed=$(( total_failed + failed ))
done

# Deliberately NO teardown here: the newest pin's stack stays up, which is what
# `make test-benchmark` and a follow-up `make test-integration` expect to find.
# `make stack-destroy` when you want the disk back.

# --- verdict ----------------------------------------------------------------
version_count="$(printf '%s\n' $ordered | wc -l | tr -d ' ')"
echo
echo "Integration matrix ($version_count versions, oldest first: $ordered)"
printf '%s\n' "$results" | sed '/^$/d'
# One aggregate line, in pytest's own shape, so a caller that parses the tail of
# this log (the DoD gate does) sees the totals across every version rather than
# whichever version happened to run last.
echo "matrix total: $total_passed passed, $total_skipped skipped, $total_failed failed across $version_count versions"

if [ "$nogo" -eq 0 ]; then
  echo "VERDICT: GO (every supported Kibana line is green; the stack is left up on the newest pin)"
else
  echo "VERDICT: NO-GO"
  exit 1
fi
