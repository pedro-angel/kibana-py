#!/bin/sh
# Target-vocabulary conformance check — reference checker for the
# dev-environment-facade skill. The spec is that skill's "Enforcement"
# section; the canonical name list is its vocabulary.txt (beside this
# script here in the methodology repo; vendored under skills/ in consuming
# repos, which execute the vendored copy rather than forking it). The
# machine checks names and composition; whether same-named targets keep
# the same *promise* across sibling repos stays with review.
#
# Checks:
#   1. every universal name is a real target (make -qp database, exact
#      match) that expands to at least one command — a .PHONY ghost whose
#      rule was deleted is a no-op, not a target
#   2. no banned name is a target
#   3. for each target under a reserved prefix, its bare remainder is not a
#      target
#   4. family names are present exactly when their capability marker fires
#      (roles optional/mutating: allowed, never required)
#   5. check's floor: for every floor-role name whose capability fires, each
#      line of `make -n <name>` appears in `make -n check` — both sides
#      expanded, so leaf recipes may use make variables
#   6. no mutating-role target's expanded commands appear in `make -n check`
#      (mutating = never runs inside check)
#
# A malformed manifest (unknown tier, role, or capability token — validated
# eagerly, every row) is a hard FAIL, never a skip — this checker fails
# closed. Requires GNU make with the Makefile at the repo root. No target
# the checker expands may invoke make or carry '+' recipes (they would
# execute under -n; guarded one level into check — deeper recursion is the
# adopter's to prevent).
#
# Portable POSIX sh; zero deps beyond make/awk/grep/git/sed.
# Concept adapted from cmanaha/extended-superpowers (MIT).
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2
LC_ALL=C; export LC_ALL
manifest="${1:-skills/dev-environment-facade/vocabulary.txt}"
[ -f "$manifest" ] || { echo "FAIL: no vocabulary manifest at: $manifest"; exit 2; }

fail=0
bad() { echo "  NO-GO $1"; fail=1; }
ok()  { echo "  GO    $1"; }
die() { echo "FAIL: $1"; exit 2; }
tab=$(printf '\t')

# Normalized manifest: CRs and trailing whitespace stripped so a CRLF file or
# a stray space can never silently drop a row's tier or role. Reading it back
# through a here-doc also guarantees the last row survives a missing final
# newline.
cleaned=$(sed -e 's/[[:space:]]*$//' "$manifest")   # CR is in [[:space:]]

# Eager token validation — junk in the capability column is a hard error on
# every row, even ones whose checks never consume the token.
while IFS="$tab" read -r tier name cap role; do
  case "$tier" in ''|\#*|prefix) continue ;; esac
  case "${cap:--}" in
    -|stack|suite|ship|analyzers|autofix|deps|source|hookcfg|docs|env) : ;;
    *) die "unknown capability token in manifest row '$tier $name': '$cap'" ;;
  esac
done <<EOF
$cleaned
EOF

# --- target namespace: make -qp's database. -q is question mode and exits
# nonzero under a phony default goal by design — parse output, ignore that
# status; an empty database is a hard failure, not a sea of missing names.
db=$(make -qp 2>/dev/null)
targets=$(printf '%s\n' "$db" | awk '
  /^# Not a target/ { skip = 1; next }
  /^# Files/        { infiles = 1; next }
  /^# Finished Make data base/ { infiles = 0 }
  !infiles { next }
  skip { skip = 0; next }
  /^[a-zA-Z0-9][a-zA-Z0-9._-]*:/ { sub(/:.*/, ""); print }' | sort -u)
[ -n "$targets" ] || die "could not parse any targets from 'make -qp' (broken or missing Makefile?)"

has_target() { printf '%s\n' "$targets" | grep -qFx "$1"; }

# raw recipe lines of one target from the database (tab stripped, echo
# prefixes kept — only the recursive-make guard consumes this). make -p
# interleaves "#  ..." comment lines between the target and its recipe —
# skip them; any other non-tab line ends the entry.
recipe_of() {
  printf '%s\n' "$db" | awk -v t="$1" '
    index($0, t ":") == 1 { f = 1; next }
    f && /^#/ { next }
    f && /^\t/ { sub(/^\t/, ""); print; next }
    f { f = 0 }'
}

# expanded commands of one target: everything `make -n <t>` would run for
# t's dependency closure, with make's own chatter — and nothing else —
# filtered: the anchor matches "make: ..." / "make[1]: ..." only, so a
# recipe line that literally starts with "make" survives (and is refused
# by the guard below). Both sides of the floor comparison use this, so
# leaf recipes may use make variables.
nrun_of() {
  make -n "$1" 2>/dev/null | grep -v '^make\(\[[0-9]*\]\)\{0,1\}: '
}

# refuse recipes the expansion cannot handle, for two distinct reasons:
# $(MAKE)/${MAKE} and '+'-marked lines (any prefix order) EXECUTE under -n;
# a literal make invocation does not execute, but its sub-make output would
# be indistinguishable from make's own chatter and defeat the filter.
# Called on every target the checker expands, plus check's direct
# prerequisites; deeper recursion is the adopter's responsibility ($(shell)
# already runs at -qp parse time — full read-only-ness is unattainable).
guard_no_make() {
  if recipe_of "$1" | grep -qE '\$[({]MAKE[)}]|^[@+-]*\+|^[@+-]*make[[:space:]]'; then
    die "make-invoking or '+' recipe in '$1' — \$(MAKE)/+ execute under -n, literal make defeats the chatter filter; unsupported"
  fi
}

# true when ANY argument glob matched (an unmatched glob stays a literal
# word that -e rejects) — `ls glob1 glob2` is wrong here: it exits nonzero
# when any one glob fails, even if another matched.
any_glob() {
  for _f in "$@"; do [ -e "$_f" ] && return 0; done
  return 1
}

# --- capability markers (tokens defined in the skill's Enforcement section).
# Positional params only — no shared-name globals, so the autofix recursion
# and the manifest read loop cannot clobber each other.
fires() { # fires <capability> <name>
  case "$1" in
    -) return 0 ;;                       # always fires
    stack)
      any_glob docker-compose.yml docker-compose.yaml compose.yml \
        compose.yaml */docker-compose.yml */docker-compose.yaml \
        */compose.yml */compose.yaml && return 0
      any_glob ./*stack*.sh scripts/*stack*.sh && return 0
      return 1 ;;
    suite)                               # the tier's suite is registered:
      _tier="${2#test-}"                 # a tests/<tier> dir or test marker
      [ -d "tests/$_tier" ] && return 0  # (quoted toml or bare ini style)
      grep -qE "^[[:space:]]*[\"']?$_tier:" pyproject.toml setup.cfg \
        pytest.ini 2>/dev/null && return 0
      return 1 ;;
    ship)
      grep -q '^\[project\]' pyproject.toml 2>/dev/null && return 0
      [ -f package.json ] && return 0
      any_glob Dockerfile */Dockerfile && return 0
      return 1 ;;
    analyzers)                           # analyzer config outside the hook config
      # (reference scope: ruff/mypy/import-linter — extend as analyzers arrive)
      grep -qE '^\[tool\.(ruff|mypy|importlinter)' pyproject.toml 2>/dev/null \
        && return 0
      [ -f ruff.toml ] || [ -f mypy.ini ] || [ -f .importlinter ] && return 0
      return 1 ;;
    autofix)                             # any analyzer or hook config offering
      fires analyzers "$2" && return 0                          # auto-fixes
      fires hookcfg "$2" ;;              # (proxy: doesn't probe for actual
                                         # fixers — only widens allowed-not-
                                         # required, so over-firing is safe)
    deps)  [ -f uv.lock ] || [ -f poetry.lock ] || [ -f package-lock.json ] \
             || [ -f requirements.txt ] || [ -f pyproject.toml ] \
             || [ -f package.json ] ;;
    source)                              # first-party code, any layout
      [ -d src ] || [ -d lib ] && return 0
      for _p in ./*/__init__.py; do      # flat layout — skip conventional
        case "$_p" in                    # non-shipped dirs
          ./tests/*|./test/*|./docs/*|./examples/*) continue ;;
        esac
        [ -e "$_p" ] && return 0
      done
      # packaging claims shippable code we cannot locate — refuse to guess
      if grep -q '^\[project\]' pyproject.toml 2>/dev/null \
        || [ -f package.json ]; then
        die "source token: first-party layout undetermined (no src/, lib/, or */__init__.py) — sast scope falls to review"
      fi
      return 1 ;;
    hookcfg) [ -f .pre-commit-config.yaml ] || [ -f lefthook.yml ] \
               || [ -d .husky ] ;;
    docs)  [ -f mkdocs.yml ] || [ -f mkdocs.yaml ] || [ -d docs/source ] ;;
    env)   [ -f uv.lock ] || [ -f poetry.lock ] || [ -f pyproject.toml ] \
             || [ -f package.json ] ;;
    *)     die "unknown capability token in manifest: '$1'" ;;
  esac
}

echo "Vocabulary conformance ($manifest)"

# --- 1/2/4: universal, banned, family requiredness --------------------------
while IFS="$tab" read -r tier name cap role; do
  case "$tier" in ''|\#*) continue ;; esac
  case "${role:-}" in ''|floor|optional|mutating) : ;;
    *) die "unknown role in manifest row '$tier $name': '$role'" ;;
  esac
  case "$tier" in
    universal)
      if has_target "$name"; then
        guard_no_make "$name"
        if [ -n "$(nrun_of "$name")" ]; then ok "universal: $name"
        else bad "universal target is a no-op: $name (expands to no commands)"
        fi
      else bad "universal target missing: $name"; fi ;;
    banned)
      if has_target "$name"; then bad "banned target present: $name"; fi ;;
    family)
      required=1
      case "${role:-}" in optional|mutating) required=0 ;; esac
      if fires "${cap:--}" "$name"; then
        if has_target "$name"; then ok "family: $name (capability: ${cap})"
        elif [ "$required" -eq 1 ]; then
          bad "family target missing: $name (capability '${cap}' fires)"
        fi                               # optional/mutating: allowed, not required
      else
        if has_target "$name"; then
          bad "family target present without its capability: $name"
        fi
      fi ;;
    prefix) : ;;                         # consumed by the bare-remainder scan
    *) die "unknown tier in manifest: '$tier'" ;;
  esac
done <<EOF
$cleaned
EOF

# --- 3: bare remainders under reserved prefixes ------------------------------
for p in $(printf '%s\n' "$cleaned" | awk -F"$tab" '$1 == "prefix" { print $2 }'); do
  for t in $(printf '%s\n' "$targets" | awk -v p="$p" 'index($0, p) == 1'); do
    bare="${t#"$p"}"
    if [ -n "$bare" ] && has_target "$bare"; then
      bad "bare remainder of $t is a target: $bare"
    fi
  done
done

# --- guard check's composition before expanding it (one level: check plus
# its direct prerequisites; every other expanded target is guarded at its
# own use site).
check_prereqs=$(printf '%s\n' "$db" | awk -F: '/^check:/ { print $2; exit }')
for t in check $check_prereqs; do
  guard_no_make "$t"
done

# --- 5: check's floor, expanded on both sides ---------------------------------
# (here-docs, not pipes: the loops must run in this shell so bad() sticks)
ncheck=$(nrun_of check)
floorlist=$(printf '%s\n' "$cleaned" |
  awk -F"$tab" '$4 == "floor" { print $2 "\t" $3 }')
while IFS="$tab" read -r name cap; do
  [ -n "$name" ] || continue
  fires "${cap:--}" "$name" || continue
  has_target "$name" && guard_no_make "$name"
  cmds=$(nrun_of "$name")
  if [ -z "$cmds" ]; then
    bad "floor: $name expands to no commands"
    continue
  fi
  missing=0
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    printf '%s\n' "$ncheck" | grep -Fxq "$line" || missing=1
  done <<EOF2
$cmds
EOF2
  if [ "$missing" -eq 0 ]; then ok "floor: $name in check's expansion"
  else bad "floor: $name's commands missing from 'make -n check'"; fi
done <<EOF
$floorlist
EOF

# --- 6: mutating-role targets must never run inside check --------------------
# Expanded like the floor. A mutating target sharing a prerequisite with
# check would false-flag here — that fails red, not open, and stays visible.
for name in $(printf '%s\n' "$cleaned" |
  awk -F"$tab" '$4 == "mutating" { print $2 }'); do
  has_target "$name" || continue         # target absent — nothing to assert
  guard_no_make "$name"
  cmds=$(nrun_of "$name")
  [ -n "$cmds" ] || continue
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    if printf '%s\n' "$ncheck" | grep -Fxq "$line"; then
      bad "mutating target $name's commands run inside check"
      break
    fi
  done <<EOF
$cmds
EOF
done

if [ "$fail" -eq 0 ]; then
  echo "VERDICT: CONFORMANT"
else
  echo "VERDICT: NOT CONFORMANT"
  exit 1
fi
