#!/bin/sh
# Definition-of-Done gate: tooling-certified GO/NO-GO over the criteria declared in
# dod.config. The author (human or agent) never self-certifies "done" — this script
# does. Run it before claiming completion and ALWAYS before a release.
#
# Each criterion delegates to its make leaf, so the command strings live exactly
# once, in the Makefile recipes (this repo's leaves use $(VENV_BIN) variables, which
# a shell mirror could never keep byte-identical — delegation is the mirror).
# Criteria marked `required` must pass; `n/a` are skipped (declare, don't delete, so
# the omission is a visible decision). Full logs land in /tmp/dod-<criterion>.log.
# integration/benchmark need the local Elastic Stack (their make targets start it —
# docker required); test-python-matrix uses pyenv-installed interpreters when
# available. CI runs the fast criteria on every PR; this gate is the superset a
# human runs where the infrastructure lives.
#
# Portable POSIX sh; zero deps beyond make and the project venv.
# Concept adapted from cmanaha/extended-superpowers (MIT).
set -u
# The criteria delegate to child `make` invocations: a leaked MAKEFLAGS from a
# parent make (`make -i dod`, `-k`, `-j` jobserver) would make children ignore
# recipe errors and flip the gate to a false GO — demonstrated, so cleared.
unset MAKEFLAGS MFLAGS
cd "$(git rev-parse --show-toplevel)" || exit 2
cfg="${1:-dod.config}"
[ -f "$cfg" ] || { echo "FAIL: no DoD config found at: $cfg"; exit 2; }

# Fail closed on config typos: every row must be a known criterion set to
# `required` or `n/a` — a misspelled value must never silently skip a gate.
known="unit_green types_clean hygiene_hooks audit_clean sast_clean docs_strict \
vocabulary_conformant integration_green benchmark_green matrix_green changelog_entry"
while IFS= read -r line; do
  case "$line" in ''|\#*) continue ;; esac
  crit=$(printf '%s' "$line" | sed 's/[[:space:]]*=.*//')
  val=$(printf '%s' "$line" | sed 's/.*=[[:space:]]*//; s/[[:space:]]*$//')
  case " $known " in *" $crit "*) : ;; *) echo "FAIL: unknown criterion in $cfg: '$crit'"; exit 2 ;; esac
  case "$val" in required|n/a) : ;; *) echo "FAIL: criterion '$crit' has invalid value '$val' (use: required | n/a)"; exit 2 ;; esac
done <"$cfg"

req()    { grep -qE "^$1[[:space:]]*=[[:space:]]*required([[:space:]]|$)" "$cfg"; }
nogo=0
logdir="/tmp/dod-$(basename "$(pwd)")"   # per-repo: sibling gates share /tmp
mkdir -p "$logdir"
run() {
  name="$1"; shift
  if "$@" >"$logdir/$name.log" 2>&1; then
    echo "  GO    $name"
  else
    echo "  NO-GO $name  (log: $logdir/$name.log)"
    nogo=1
  fi
}

echo "Definition-of-Done gate ($cfg)"

if req unit_green;             then run unit_green             make test; fi
if req types_clean;            then run types_clean            make lint; fi
if req hygiene_hooks;          then run hygiene_hooks          make hooks; fi
if req audit_clean;            then run audit_clean            make audit; fi
if req sast_clean;             then run sast_clean             make sast; fi
if req docs_strict;            then run docs_strict            make docs; fi
if req vocabulary_conformant;  then run vocabulary_conformant  skills/dev-environment-facade/vocabulary-conformance.sh; fi
if req integration_green;      then run integration_green      make test-integration; fi
if req benchmark_green;        then run benchmark_green        make test-benchmark; fi
if req matrix_green;           then run matrix_green           make test-python-matrix; fi

if req changelog_entry; then
  if [ -f CHANGELOG.md ] && grep -qiE '^## (\[?unreleased|\[?[0-9]+\.[0-9]+\.[0-9]+)' CHANGELOG.md; then
    echo "  GO    changelog_entry"
  else
    echo "  NO-GO changelog_entry  (CHANGELOG.md missing or has no release section)"
    nogo=1
  fi
fi

if [ "$nogo" -eq 0 ]; then
  echo "VERDICT: GO"
else
  echo "VERDICT: NO-GO (fix the criteria above, or mark them n/a in $cfg as a visible decision)"
  exit 1
fi
