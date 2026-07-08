---
name: additive-default-off-feature-flags
description: Use when adding any new capability to a working system — ship it behind a flag or optional collaborator that defaults to prior behavior.
---

# Add Capabilities Behind Default-Off Seams

When you introduce a new capability to a system that already works, gate it behind a switch whose default reproduces the existing behavior exactly. The proven path stays untouched; the new path is opt-in, reversible, and carries no standing cost until someone deliberately turns it on.

## When to use

Apply this whenever you add a feature to code, infrastructure, or a pipeline that real users or other systems already depend on:

- A new collaborator (cache, verifier, retriever, telemetry sink) wired into an existing flow.
- A new infrastructure component (a managed database, a queue, an extra service) added to a running deployment.
- A behavior change you believe is an improvement but have not yet proven against the baseline.

Red-flag thoughts that mean STOP and apply this skill:

- "It's the plan, so I'll just turn it on." (Being planned is not the same as being proven.)
- "I'll update the existing tests to match the new behavior." (You're about to erase the baseline's safety net.)
- "It's obviously better, no need to keep the old path." (Then it survives a default-off rollout trivially — do that.)
- "I'll rewrite the call sites to use the new thing." (That's a forced migration, not an additive seam.)

## The rule

1. **Add a seam, not a rewrite.** Introduce the feature as an optional parameter, an injected collaborator, or an environment / infrastructure selector — never by editing existing call sites to force the new path.
2. **Make the default reproduce today's behavior exactly.** The off state must be byte-for-byte the current system: `cache=None`, `verify=False`, `RAG_ENABLED=false`, `TELEMETRY_ENABLED=false`, `enable_cloud_sql=false`. If the default changes any observable behavior, it is not default-off.
3. **Default to the lowest-cost posture.** The baseline should carry zero standing cost from a feature nobody has enabled — no idle instances, no always-on sampling, no provisioned resource sitting unused.
4. **Keep every existing test green without modification.** This is the proof that the old path is untouched. If you find yourself editing an existing test, stop — you've changed the default. Add *new* tests for the *new* path instead.
5. **Gate twice when risk is high.** For experimental work, require two independent conditions before the new path runs — e.g. the flag is set AND the prerequisite artifact exists (an index file, a migrated table, a reachable endpoint). A missing prerequisite must fall back to baseline, not crash.
6. **Make the safety property explicit.** Write in the spec, PR description, or changelog: *"the default preserves current behaviour and tests."* This tells reviewers what to verify and commits you to it.
7. **Keep it reversible.** Removing the flag or collaborator must restore the baseline with no further code surgery. If deletion would require untangling, the seam was not clean.

## Why

A working system is an asset you've already paid for in testing, debugging, and user trust. A new feature is a hypothesis. Coupling the hypothesis to the asset means a flaw in the new code becomes an outage in the proven code — and the only way back is a revert under pressure. A default-off seam decouples the two: you can merge, deploy, and even ship the new path to a fraction of traffic while the baseline keeps serving everyone else. Reversal is flipping a switch, not a rollback. The cost of skipping this is paid exactly when you can least afford it — in production, on the path everyone relied on.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent deployed to a cloud platform — a cost-tracking cache was added to the core use case as an optional collaborator. The design note stated plainly: *"Default None preserves current behaviour and tests"* (cost-cache design spec, §3). With `cache=None`, the use case ran exactly as before and its entire existing test suite passed unmodified; only the cache-enabled path got new tests.

The same team applied the second condition on a retrieval-augmented feature, documenting that *"the feature is purely additive and off by default"* (retrieval doc, §Wiring) and gating it on both `RAG_ENABLED` being true *and* the index file existing — so an unconfigured or half-provisioned environment silently fell back to the baseline rather than failing.

The discipline also caught a regression: an evaluation harness showed that a "skeptic verify" pass *regressed* quality (eval calibration record, §judge-calibration: skeptic pass REGRESSES → SHIPPED OFF; temperature 0.2 shipped as the measured win). Because it had been built as a default-off seam, shipping it OFF cost nothing, and the measured win (a low-temperature setting) was shipped in its place. Had verify been on by default "because it was the plan," the baseline would have shipped worse. You do not need to know any of this project's specifics to apply the pattern: optional collaborator, default = prior behavior, old tests green, double-gate the risky bit.

## Anti-patterns

- Turning a new, unproven feature on by default and destabilizing the baseline.
- Rewriting existing call sites to force the new behavior instead of adding an opt-in seam.
- Editing existing tests to accommodate the new default rather than keeping the old path green.
- Shipping a regressing idea on by default because "it was the plan," even after a harness flagged the regression.

---

Related skills:

- [hexagonal-with-enforced-contracts](../hexagonal-with-enforced-contracts/SKILL.md)
- [grounded-verifiable-gates](../grounded-verifiable-gates/SKILL.md)
- [configuration-single-source-of-truth](../configuration-single-source-of-truth/SKILL.md)
- [surgical-changes-with-checkpoints](../surgical-changes-with-checkpoints/SKILL.md)
