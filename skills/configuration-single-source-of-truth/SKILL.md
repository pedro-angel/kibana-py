---
name: configuration-single-source-of-truth
description: Use when a value (project id, model, threshold, rubric) would be duplicated across Makefile, scripts, docs, and code — collapse to one source.
---

# One Canonical Config Source, Everything Derives

Every fact lives in exactly one place; everyone else reads or derives it. A value that appears in two files is a future bug — the two copies will drift, and the drift will be silent.

## When to use

Reach for this the moment a single value needs to be known by more than one consumer — build scripts, runtime code, docs, CI, and humans.

Red-flag thoughts that mean STOP and apply this skill:

- "I'll just paste the project id / model name into the README example too."
- "I'll hardcode the threshold here for now and remember to change both."
- "The docs table is a bit stale but close enough."
- "These two enums happen to match, so it's fine."
- "I'll pass `PROJECT=<id>` on the command line every time."
- "It's only tuning — I'll bury it in the code as a constant."
- "I'll re-list those dependencies in this extra / that requirements file — same versions anyway."

## The rule

1. **Name one canonical location per fact.** Decide where the truth lives — an env var, a single YAML key, one constant module. Write it down. Everything else points at it.
2. **Make consumers derive, never re-declare.** Build scripts, code, and CI read the canonical value (parse the file, import the constant, read the env var). No second hand-typed copy anywhere.
3. **Guard with fail-fast.** When the canonical value is unset or still a placeholder, exit non-zero with an actionable message ("CLOUD_PROJECT is unset; set it in .env"). A missing value should stop the run, not silently default.
4. **Separate "tune in config" from "change code to extend."** Behavior knobs — weights, prompts, decision thresholds, rubrics — go in one config file (e.g. YAML), so recalibrating is a config edit with zero code change. Draw the line explicitly and document it: what you tune vs. what requires a code change.
5. **Declare one source authoritative; stop hand-maintaining parallel copies.** Point docs, tables, and examples at the canonical config and say it is the source of truth — generate them from code or config where that is feasible. Never keep a hand-maintained copy that can drift from it. This applies to release and documentation metadata as much as to config values: a version string, a coverage count, a supported-matrix table tends to sprawl across a version file, the README, a CHANGELOG, and a docs site — keep one source authoritative and derive or check the rest, because the surface a release forgets to update is precisely the one that silently goes stale.
6. **Ship a non-secret template.** Commit `.env.example` (or equivalent) as the documented config surface, one inline comment of rationale per knob. It is the contract; secrets stay out of version control.
7. **Resolve env-over-file at composition time.** When the same fact can come from the process environment or a file, let the real environment win and fall back to the file — resolve it once, at startup/composition, not scattered through the code.
8. **If a fact truly must live in two places, couple them explicitly and guard it.** Add a check that validates one against the other (e.g. assert the code enum equals the YAML keys) so they cannot diverge without a loud failure.
9. **Dependency manifests are configuration — declare each dependency and tool version once.** Compose aggregate groups by reference (an `all` extra that references the feature extras) instead of re-listing pins; delete satellite requirements files that shadow the canonical manifest; and give each tool exactly one version owner — whoever *executes* the tool owns its version (if the hook runner pins the linter, remove the linter from the dev manifest and drop the duplicate CI step that ran it at another version). Then make sure update automation watches every surface that still declares anything: a bot that bumps one copy of a duplicated pin doesn't update your dependency, it forks it.

## Why

The "single source of truth" headline is the obvious part. The earned, non-obvious payload is three patterns. (1) **Tune-vs-extend split** (rule 4): draw a hard line between what you recalibrate in config and what requires a code change, so moving a threshold is a one-file diff a non-engineer can review and nobody reaches into the source tree to do it. (2) **Env-over-file at composition time** (rule 7): resolve the same fact once at startup, letting the real deployment environment win and the file act only as the fallback. (3) **Guard the unavoidable duplicate** (rule 8): when a fact genuinely lives in more than one place, pick the canonical copy and check the others against it — turning silent drift into a loud, located failure, where you can. The failure this prevents is specific: duplicated copies start identical, so tests pass and reviews approve; months later someone edits one and not the other, the system runs with two "truths," and it fails far from the edit.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent deployed to a cloud platform — the cloud project id lived in exactly one spot: `CLOUD_PROJECT` in `.env`. The build file derived it (`PROJECT ?= $(strip $(shell sed -n 's/^CLOUD_PROJECT=//p' .env ...))`) instead of asking the operator to type it on every command, and a require-project guard would `exit 1` with a clear message if it was still unset — so a misconfigured deploy stopped at the gate instead of half-running against the wrong project. Separately, the LLM-judge's four scoring dimensions — their weights and per-dimension prompt templates — sat in `config/rubric.yaml` as configuration, not code, so calibration never touched a source file. The canonical list of those dimensions was the `RUBRIC_DIMENSIONS` tuple in `domain/scoring.py`, but the fact actually lived in *three* places: that tuple, the structured-output schema's `enum` in the evaluation use-case module, and the YAML keys — `docs/EXTENDING.md` calls adding a dimension "a coordinated change across three places." Only one of those couplings carries the loud guard rule 8 wants: the rubric loader rejects any YAML whose keys are not exactly `RUBRIC_DIMENSIONS`. The schema enum is a third, hand-typed copy with no test asserting it equals the canonical tuple — it stays in sync by that documented coordination, not by an assertion. That is the honest shape of rule 8 here: guard the pair you can, and where you cannot yet, make the manual coupling explicit in the docs. You can apply all of this without knowing that project: one location, derived consumers, a fail-fast guard, behavior in config, and — wherever a fact is unavoidably duplicated — a coupling that is guarded where you can and documented where you cannot.

## Anti-patterns

- Passing `PROJECT=<id>` on every invocation and copy-pasting it into four doc examples.
- Burying tunable thresholds or prompts inside code strings, so recalibration means a code change and a deploy.
- Maintaining a hand-written env table in the docs that drifts from the actual config defaults.
- Duplicating a value in two files with no guard against them diverging.
- Bumping the version and one changelog while a second changelog surface (a docs site) silently stays a release behind.
- Re-listing the same dependencies in an aggregate extra, a satellite requirements file, and a hook config — then letting an update bot bump one of the three.

---

Related skills:

- [../hexagonal-with-enforced-contracts/SKILL.md](../hexagonal-with-enforced-contracts/SKILL.md)
- [../secrets-and-teardown-discipline/SKILL.md](../secrets-and-teardown-discipline/SKILL.md)
- [../docs-as-deliverable/SKILL.md](../docs-as-deliverable/SKILL.md)
- [../additive-default-off-feature-flags/SKILL.md](../additive-default-off-feature-flags/SKILL.md)
