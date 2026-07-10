# Identity Hygiene & Evidence-over-Deference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax. This plan is executed inline by the authoring session (secret-handling stays in one context).

**Goal:** Make private-identifier leaks un-committable (derived + registry pre-commit check), scrub the existing leak forward, and encode "pin the run, not the runner" + a new evidence-over-deference skill in agent-methodology.

**Spec:** `docs/superpowers/specs/2026-07-10-identity-hygiene-and-evidence-over-deference-design.md` (approved).

## Global Constraints

- The leaked hostname must NEVER appear in: this plan, any commit message, any PR body, any file of any repo. Refer to it as "the private hostname". It may exist only in: the local registry file (outside all repos) and transient battle-test scratch files that are never staged for a real commit.
- All commits: Conventional-Commit + provenance trailers in ONE `-m` block (`Co-Authored-By` + `Claude-Session` separated by a plain newline — the pack repos parse only the final trailer paragraph).
- POSIX sh, zero runtime deps for the hook. Fail-closed semantics per spec D2.
- New skill frontmatter: `name: evidence-over-deference`, description starts "Use when" (repo gate).
- PR merges await explicit user approval per repo.

---

### Task 1: `check-no-private-identifiers.sh` in git-controls-starter

**Files:**
- Create: `git-controls-starter/scripts/checks/check-no-private-identifiers.sh` (+x)
- Modify: `git-controls-starter/.pre-commit-config.yaml` (register, enabled)
- Modify: `git-controls-starter/README.md` (tree + control bullet + registry setup)

**Hook source (complete):**

```sh
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
  case "$t" in "" | localhost | ? | ??) return ;; esac # skip empty/short/common
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
```

**Registration** (after `check-one-pin-per-action`):

```yaml
      - id: check-no-private-identifiers
        name: "no private identifier (hostname, internal name) enters the repo"
        language: script
        entry: scripts/checks/check-no-private-identifiers.sh
        pass_filenames: false
```

- [ ] Write script (+x), register, README (tree entry; bullet: derived Tier-1 + outside-repo registry + allowlist escape; setup: `mkdir -p ~/.config/git-controls && $EDITOR .../private-identifiers`).
- [ ] Battle-test all modes on a scratch branch: clean tree → pass; staged file w/ own hostname → FAIL; registry entry staged → FAIL; allowlisted pair → pass; `PRIVATE_IDENTIFIERS_FILE=/nonexistent` → FAIL; nothing staged → tree mode runs.
- [ ] `pre-commit run --all-files` green; commit `feat: add check-no-private-identifiers invariant (derived + registry deny, allowlist escape)`; push; PR.

### Task 2: agent-methodology — amendments + new skill

**Files:** `skills/battle-testing-on-real-infra/SKILL.md`, `skills/secrets-and-teardown-discipline/SKILL.md`, `skills/evidence-over-deference/SKILL.md` (new), `AGENTS.md`, `README.md`, `adapters/*` (4).

- [ ] battle-testing rule 4: append "pin the run, not the runner" (properties yes / identity no / role names / litmus test); red flag `"the evidence is more credible with the real hostname"`; anti-pattern; In-practice sentence (role-named incident).
- [ ] secrets-and-teardown: broaden intro + one rule clause to "credentials and identifying details"; name derived+registry hook as mechanism; anti-pattern.
- [ ] New skill per spec D4.3 (full standard structure, In-practice = this incident by role).
- [ ] AGENTS.md: index paragraph + link; README: index row; all 4 adapters: enumerate the new skill (read one adapter first to learn its format).
- [ ] Full pre-commit (15 gates incl. frontmatter/index/adapters/crosslinks) green; per-reason commits; push; PR; Issue #4 comment (enforcement entry + mirror-rides-Issue-4 note).

### Task 3: kibana-py — scrub, adopt, re-sync

- [ ] Seed local registry (`~/.config/git-controls/private-identifiers`) with the private hostname. NOT in any commit.
- [ ] Scrub `docs/evidence/cross-arch-x86_64-0.3.1.md:9` → role + properties (spec D1 text). Commit FIRST (added-lines scan keeps this passing even with hook active).
- [ ] Vendor hook into `scripts/checks/` + register in `.pre-commit-config.yaml`; battle-test: scratch file w/ private hostname staged → commit blocked (proof of un-committability); `git grep -i` for it → empty.
- [ ] Re-sync vendored methodology (`AGENTS.md`, `skills/`, `.claude/skills/`) from the Task-2 branch tree (includes this week's sharpenings + new skill). Verify no drift: `diff -r`.
- [ ] `pre-commit run --all-files` green; per-reason commits; push; PR (body: exposure map, no history rewrite rationale).

### Task 4: Deliver

- [ ] CI green on all three PRs; report with per-repo merge asks (user approves merges).
