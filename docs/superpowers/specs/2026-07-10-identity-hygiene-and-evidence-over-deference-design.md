# Identity Hygiene & Evidence-over-Deference — Design

**Date:** 2026-07-10
**Status:** Approved design, pending spec review
**Scope:** kibana-py (remediation + adoption), git-controls-starter (the check), agent-methodology (two skill amendments + one new skill)

## Context

The hostname of a private test machine was found committed in
`docs/evidence/cross-arch-x86_64-0.3.1.md:9` (introduced by `40cf87f`). Forensics
established the exposure map: the published PyPI sdist/wheel, the GitHub release
assets, and Read the Docs are all **clean** (the sdist ships no `docs/`; RTD builds
only `docs/source/`). The name exists in exactly one tracked file and one commit of
the public repo. Remediation decision: **scrub forward only** — the history residual
is accepted as low-severity for a personal LAN host with no public DNS.

**Root cause:** the methodology itself pushed toward the leak.
`battle-testing-on-real-infra` rule 4 rewards specificity in evidence artifacts
("pin the exact command, the backends/endpoints used") with no counterweight
distinguishing a host's *properties* (arch, OS, kernel — reproducibility-relevant)
from its *identity* (hostname, username, home path, non-public IPs — pure
reconnaissance data). No gate could object: the secret checks know key material and
secret-looking filenames, not identity strings.

**The design insight:** "is this identifier allowed here?" is context-dependent, but
the class splits into three tiers, two of which are mechanically enforceable:

| Tier | What | Enforcement |
|---|---|---|
| 1 | The authoring machine's own identity (`hostname -s`/`-f`) | **Derived** at hook runtime — zero config |
| 2 | Known private infrastructure (other hosts, internal domains) | **Registry** outside any repo; never committed |
| 3 | Everything else | **Judgment rule** for the author/agent + fail-toward-ask escape |

The Tier-3 litmus test: *would the artifact prove the same claim with the identifier
replaced by a role? Then the identifier is leakage.*

A second finding rode along: nothing in the pack tells an agent to **challenge the
human with evidence before complying**. This session's productive collisions (in both
directions) motivated encoding it as a full skill.

## Design

### D1 — Remediation (kibana-py)

Edit `docs/evidence/cross-arch-x86_64-0.3.1.md:9`: replace the hostname with a role
name plus the properties that actually carry the evidence, e.g.
`**Host:** dedicated x86_64 verification host — Debian GNU/Linux 13 (trixie), kernel 6.12, 4 CPU / 7.7 GB RAM / Docker.`
No history rewrite (accepted residual, recorded here).

### D2 — The check (git-controls-starter)

New worked invariant `scripts/checks/check-no-private-identifiers.sh`, registered
(enabled) in `.pre-commit-config.yaml`, POSIX sh, zero deps:

- **Input scanned:** **added lines only** of the staged diff
  (`git diff --cached -U0`, `+` lines), case-insensitive whole-word match. Added-only
  matters: scanning removed lines would block the very commit that scrubs a leaked
  identifier out.
- **Tier 1 (always on):** deny the machine's own `hostname -s` and `hostname -f`
  (skip values that are common non-identifying strings: `localhost`, names < 3 chars).
- **Tier 2 (registry):** deny every entry in `~/.config/git-controls/private-identifiers`
  (one identifier per line, `#` comments). Override path via
  `PRIVATE_IDENTIFIERS_FILE`. Absent file → tier skipped (Tier 1 still runs);
  **configured-but-unreadable → FAIL (fail-closed)**.
- **Escape (Tier 3 is judgment):** a repo-tracked allowlist
  `.private-identifiers-allow` listing `<identifier> <path-glob>` pairs for the rare
  legitimate use — the guard fails toward asking, never silently.
- README: new bullet under "What each control buys you" + registry setup note,
  including *why* the registry lives outside the repo (the list itself is the secret).

### D3 — Adoption (kibana-py)

- Vendor the hook into `scripts/checks/` and register it in `.pre-commit-config.yaml`
  (kibana-py already vendors the pack's controls).
- Seed this machine's registry with the private hostname (local file, never
  committed) — after which a re-leak is physically un-committable here.
- Battle-test the hook in both directions: staged file containing the registry entry
  → commit blocked; after scrub → suite green.
- Re-sync the vendored methodology (`AGENTS.md`, `skills/`, `.claude/skills/`) from
  upstream main — the vendored copies pre-date this week's five sharpenings — and
  include the two amendments and the new skill from D4.

### D4 — Methodology (agent-methodology)

1. **`battle-testing-on-real-infra` rule 4 amendment — "pin the run, not the runner":**
   evidence records the machine's properties (arch, OS, kernel, versions, commands,
   timings) and never its identity (hostname, username, home path, non-public IPs);
   use role names ("the x86_64 verification host"). Include the litmus test. Add the
   red-flag thought and anti-pattern; In-practice gains this incident (described by
   role, naturally).
2. **`secrets-and-teardown-discipline` broadening:** scope becomes "credentials and
   identifying details"; names the derived-denylist + private-registry hook as the
   structural mechanism ("the registry lives outside the repo because the list itself
   is the secret").
3. **New skill `evidence-over-deference`** (15th), standard structure, frontmatter
   `name: evidence-over-deference`, description starting "Use when". Core rules:
   - Verify a checkable premise before executing a request that rests on it.
   - When evidence contradicts the human's premise — or the request conflicts with a
     recorded principle — say so **once**, with the evidence and a concrete
     alternative, *before* executing.
   - The human's decision wins after being heard (instruction priority intact); if
     consequential, record the dissent where the decision is recorded.
   - Challenge is symmetric: surface your own uncertainty and invite correction;
     accept counter-evidence without performative agreement.
   - No relitigating: once decided with the evidence heard, execute fully.
   - Red flags: "the user said X, so X is true"; "easier to just do it"; "they're
     the boss" as a reason to skip a ten-second check; performative agreement.
   - In practice: this incident — the human's "not sure how to enforce it" premise
     was challenged with the three-tier split; the human's challenge of the pack's
     completeness produced this skill.
   Satisfies all repo gates: AGENTS.md index paragraph + link, README index row, all
   four adapters' enumerations updated.
4. **Issue #4 comment:** enforcement entry for the new check + note that mirroring it
   into agent-methodology root/`templates/git-controls` rides the Issue-4 rollout
   (not this change).

## Non-goals

- No git-history rewrite; no GitHub support purge (residual accepted and recorded).
- No mirroring of the new hook into agent-methodology's own root/template controls in
  this change (Issue #4 rollout).
- No LLM-based leak scanner: a deterministic hook plus a judgment rule matches
  `grounded-verifiable-gates`' preference for deterministic gates; an advisory
  agent-review pass may be proposed later in Issue #4.

## Verification

1. Hook unit exercise in the starter, all modes: Tier-1 self-hostname staged → FAIL;
   registry entry staged → FAIL; allowlisted pair → pass; registry configured but
   unreadable → FAIL; no registry → Tier 1 only; clean tree → pass.
2. kibana-py: stage a file containing the private hostname → commit blocked
   (proves the incident is now un-committable); scrubbed evidence file → suite green;
   `git grep -i` for the hostname over the tree → empty.
3. All three repos: full pre-commit suite green (starter 10+1 hooks; methodology's 15
   gates incl. frontmatter/index/adapters/cross-links for the new skill).
4. PRs with CI green on all three; merges await explicit approval per repo.

## Delivery

Three PRs, dependency order: **starter** (the check) → **agent-methodology** (skill
texts + new skill) → **kibana-py** (scrub + adopt hook + vendor re-sync). Plus the
Issue #4 comment and the local registry seeding (not in any PR — it is the secret).
