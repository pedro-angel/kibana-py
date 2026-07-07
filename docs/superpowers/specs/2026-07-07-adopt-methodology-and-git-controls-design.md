# Adopt agent-methodology pack + git-controls into kibana-py

- **Date:** 2026-07-07
- **Version:** v0.1
- **Target:** repo governance — **not** shipped in the package, so **no semver impact**
  (all files land repo-only under the eventual `0.3.1` tag; the release content is the
  separate examples spec).
- **Status:** Approved in principle (user chose *vendored copy* + *full git-controls now*);
  pending user review of this written design.

## Motivation

The maintainer adopts their own portable methodology (`pedro-angel/agent-methodology`) — a
coherent move, since that pack was distilled partly from *this* build. Two decisions are
already made:

1. **Vendored copy** of the methodology pack, so it is standing guidance for every future
   session and agent, not just this task.
2. **Full git-controls now**, before the next PyPI publish — closing a real supply-chain gap
   (`release.yml` currently pins its publish actions to mutable tags).

This spec covers those two workstreams (A: git-controls, B: methodology install). The examples
UX rework is workstream C, specified separately in
`2026-07-07-examples-human-usable-cleanup-design.md`.

## Non-goals

- No change to `kibana/` library code or the shipped wheel/sdist. `AGENTS.md`, `skills/`,
  `.github/**`, and pre-commit config are all repo-only; the sdist include-list is an explicit
  allowlist (`/kibana/**`, README, LICENSE, NOTICE) and the wheel packs only `["kibana"]`, so
  these additions ship in neither. No version bump is required *for these two workstreams*.
- **Do not clobber** the repo's existing, already-good infrastructure. `test.yml`/`docs.yml`
  are already hardened (deny-all `permissions`, concurrency, SHA-pinned) and the pre-commit
  config already runs black/isort/ruff + hygiene. git-controls is applied as an **additive
  merge**, never a copy-over.
- Do not install the methodology pack's bundled `templates/git-controls/` — workstream A is the
  single git-controls source (`configuration-single-source-of-truth`); installing both would
  duplicate it.

## Workstream A — git-controls (additive merge)

Baseline already present: hardened `test.yml`/`docs.yml`; `dependabot.yml` covering pip (`/`,
`/docs`) **and** github-actions (`/`); pre-commit with hygiene + black + isort + ruff.

Gaps to close:

1. **SHA-pin `release.yml`.** It is the PyPI publisher and uses mutable refs:
   `actions/checkout@v4`, `actions/setup-python@v5`, `actions/upload-artifact@v4`,
   `actions/download-artifact@v4`, `softprops/action-gh-release@v2`,
   `pypa/gh-action-pypi-publish@release/v1`. Pin each to a full 40-hex commit SHA with a
   `# vX.Y.Z` comment. Reuse the exact SHAs `test.yml`/`docs.yml` already pin where the
   action+version matches; resolve the rest via `gh api`. Dependabot (already tracking
   github-actions) keeps the pins fresh.
2. **Extend `.pre-commit-config.yaml` (merge, keep black/isort/ruff untouched):**
   - add `default_install_hook_types: [pre-commit, commit-msg]` so a bare install wires the
     commit-msg stage;
   - add hygiene hooks `mixed-line-ending (--fix=lf)`, `check-merge-conflict`,
     `check-case-conflict`, `detect-private-key`;
   - add `conventional-pre-commit` (commit-msg stage) with the type list
     `feat fix docs chore refactor test build ci perf style revert`;
   - add two `repo: local` script hooks — `check-no-tracked-secrets` (pre-commit) and
     `check-commit-trailer` (commit-msg) — vendored under `scripts/checks/*.sh` (POSIX sh,
     zero deps), fail-closed. The trailer gate must **skip bot commits** (Dependabot) so its
     PRs aren't blocked.
3. **Local == CI.** Add a hardened `checks.yml` that runs `pre-commit run --all-files` on push/PR
   (deny-all `permissions` + `contents: read`, SHA-pinned actions, `timeout-minutes`,
   `concurrency`), so the same config gates locally and in CI. The commit-msg hooks
   (conventional prefix, trailer) are inherently local; enforce them in CI over a PR's commits
   only if we want belt-and-suspenders — decide in the plan, default to local-only.
4. **Reconcile `CONTRIBUTING.md`.** Its current commit guidance ("Add feature: …", 72-char, no
   prefix/trailer) contradicts the conventional-prefix + provenance-trailer gate — and the real
   history already uses `feat:`/`fix:`/`docs:`. Update the doc to document the prefixes and the
   trailer (`git commit -s`, or `Co-Authored-By` / `Evidence:` / `Refs:`), so the doc matches
   the enforced hook (`docs-as-deliverable`, `configuration-single-source-of-truth`).
5. **Tighten `.gitignore`.** Broaden `.env` to the `.env.*` glob with a `!*.example` allowlist,
   as defense-in-depth behind `detect-private-key` + `check-no-tracked-secrets`.
6. **`bootstrap.sh` (optional).** Vendor the starter's one-command hook installer
   (prek → pre-commit → local `.venv`) so a fresh clone wires hooks without a global install.
   Default: include it; it's inert until run.

## Workstream B — methodology pack (vendored copy)

Place, copied from `pedro-angel/agent-methodology`:

- `AGENTS.md` at repo root — the single source of truth.
- `CLAUDE.md` at repo root — the thin Claude adapter that points at `AGENTS.md` (no existing
  `CLAUDE.md`/`AGENTS.md`, so a clean add).
- `skills/<slug>/SKILL.md` — the 15 skill files at repo root `skills/`.
- `.claude/skills/` copy of the same skills, so they're natively discoverable as slash-skills in
  this project.

Scope decisions:

- **Skip the other-agent adapters** (Cursor/Copilot/Gemini) for now — YAGNI; `AGENTS.md` at root
  already serves Codex and any AGENTS.md-native tool, and the Claude adapter covers this
  workflow. Add later if a contributor uses one.
- The vendored skills are **additive** to any per-user global skills; no conflict.
- Re-sync on update by re-copying (the tradeoff we accepted vs. a submodule).

## Sequencing

1. **A — git-controls** first, so the commit-discipline gate is in force for everything after
   (dogfooding). Land as its own commit(s).
2. **B — methodology install** next.
3. **C — examples rework** (the `0.3.1` deliverable; separate spec) last.
4. **Live verify + evidence artifact, then release `0.3.1`.**

Commits stay split by reason with conventional prefixes and provenance trailers
(`surgical-changes-with-checkpoints`); the agent's existing `Co-Authored-By` trailer already
satisfies the trailer gate. Nothing is committed until the user wants to inspect.

## Verification (`grounded-verifiable-gates` — prove the gate gates)

- `pre-commit run --all-files` passes (hooks are self-consistent with the tree).
- **Prove the commit gate actually gates:** a deliberately non-conforming message (no prefix, or
  no trailer) is **rejected**; a conforming one passes. A gate everything passes is decoration.
- **`release.yml` has zero mutable refs:** every `uses:` is a 40-hex SHA; grep finds no
  `@v#`/`@release/*`/`@main` remaining.
- **Methodology install "took"** (per the pack's INSTALL verify step): files at the paths the
  agents read; a fresh-session query ("which methodology skills apply here?") cites `AGENTS.md`
  and loads the matching `SKILL.md`.
- **Nothing leaks into the package:** build sdist + wheel and confirm `AGENTS.md`/`skills/`/
  `.github` are absent (the existing `release.yml` wheel-content assertion already guards
  `tests/`/`docs/`/`examples/`).

## Methodology alignment (dogfood)

| Skill | Applied as |
| --- | --- |
| `configuration-single-source-of-truth` | One git-controls source (not the pack's copy too); `CONTRIBUTING.md` reconciled to the enforced hooks. |
| `grounded-verifiable-gates` | Prove the commit-message gate rejects a bad message, don't assume. |
| `secrets-and-teardown-discipline` | `detect-private-key` + `check-no-tracked-secrets` + `.env.*` gitignore glob. |
| `surgical-changes-with-checkpoints` | A/B/C split commits, conventional prefixes, provenance trailers, uncommitted until inspected. |
| `docs-as-deliverable` | `CONTRIBUTING.md` reconciled to what the hooks actually enforce and history already does. |
| `spec-driven-development` | This is that workstream's own spec, separate from the examples spec; reconcile onto shipped state if it diverges. |

## Open questions

- **Enforce conventional-prefix/trailer in CI over PR commits, or local-only?** Default: local
  hooks + the `checks.yml` file gate; skip a CI commit-lint pass unless the maintainer wants it.
- **Include `bootstrap.sh`?** Default yes (inert until run).

Both are low-stakes defaults; resolve in the plan or at user review.
