#!/bin/sh
# pre-commit hook: no private identifier may enter the repo.
#
# Tiers: (1) the authoring machine's own identity, DERIVED at runtime (hostname);
# (2) a user-maintained registry of private infrastructure names that lives OUTSIDE
# any repo (the list itself is the secret); (3) everything else is judgment — see the
# escape hatch below, which fails toward asking.
#
# Scans ADDED lines of the staged diff only: scanning removed lines would block the
# very commit that scrubs a leaked identifier out. When nothing is staged (CI's
# `pre-commit run --all-files`, manual runs) it scans all tracked files instead, so a
# green run never means "ran against nothing".
#
# Escape hatch: a repo-tracked `.private-identifiers-allow` with `<identifier> <glob>`
# pairs permits a specific identifier in specific paths — explicit, reviewable.
# Portable POSIX sh; zero runtime deps.
set -u

deny=""
add_term() {
  t=$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]' | tr -d ' \t')
  # Skip empty, 1-2 chars, and generic machine names: a generic name identifies
  # nothing, and (found live) a Mac named "Mac" would otherwise deny the word "Mac"
  # in every doc. Genuinely identifying short names belong in the registry.
  case "$t" in "" | ? | ?? | localhost | mac | imac | macbook | pc | desktop | laptop | server | host | computer | home) return ;; esac
  case " $deny " in *" $t "*) return ;; esac # dedup
  deny="$deny $t"
}

# Tier 1: this machine's identity (derived; zero config)
add_term "$(hostname -s 2>/dev/null || true)"
add_term "$(hostname -f 2>/dev/null || true)"

# Tier 2: private-identifier registry, outside any repo
reg="${PRIVATE_IDENTIFIERS_FILE:-$HOME/.config/git-controls/private-identifiers}"
if [ -n "${PRIVATE_IDENTIFIERS_FILE:-}" ] && [ ! -r "$reg" ]; then
  echo "FAIL: PRIVATE_IDENTIFIERS_FILE points at $reg but it is not readable (fail-closed)."
  exit 1
fi
if [ -e "$reg" ]; then
  [ -r "$reg" ] || { echo "FAIL: registry $reg exists but is not readable (fail-closed)."; exit 1; }
  while IFS= read -r line || [ -n "$line" ]; do
    add_term "${line%%#*}"
  done <"$reg"
fi

[ -n "$deny" ] || exit 0

allowed() { # $1=term $2=path -> 0 if allowlisted
  [ -f .private-identifiers-allow ] || return 1
  while IFS= read -r a || [ -n "$a" ]; do
    a=${a%%#*}
    [ -n "$a" ] || continue
    aterm=$(printf '%s' "${a%% *}" | tr '[:upper:]' '[:lower:]')
    aglob=${a#* }
    [ "$aterm" = "$1" ] || continue
    # shellcheck disable=SC2254
    case "$2" in $aglob) return 0 ;; esac
  done <.private-identifiers-allow
  return 1
}

status=0
if git diff --cached --quiet 2>/dev/null; then
  files=$(git ls-files)
  mode=tree
else
  files=$(git diff --cached --name-only --diff-filter=ACMR)
  mode=staged
fi

for f in $files; do
  if [ "$mode" = staged ]; then
    content=$(git diff --cached -U0 -- "$f" | grep '^+' | grep -v '^+++' || true)
  else
    content=$(git show ":$f" 2>/dev/null || true)
  fi
  [ -n "$content" ] || continue
  for term in $deny; do
    if printf '%s\n' "$content" | grep -Fqiw -- "$term"; then
      allowed "$term" "$f" && continue
      echo "FAIL: private identifier \"$term\" would enter $f"
      echo "  If it genuinely belongs, add '$term <path-glob>' to .private-identifiers-allow (reviewed, explicit)."
      status=1
    fi
  done
done

[ "$status" -eq 0 ] || {
  echo "Private identifiers (hostnames, internal domains) are identity, not evidence —"
  echo "record the machine's properties or a role name instead."
}
exit $status
