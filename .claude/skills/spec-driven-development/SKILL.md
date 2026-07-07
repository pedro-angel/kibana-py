---
name: spec-driven-development
description: Use when starting any non-trivial feature or project, or when docs and code have drifted — write the design chain before or alongside code and reconcile specs onto reality.
---

# Spec-Driven Development with Reconciliation

Author an ordered design chain — BRIEF → RESEARCH → SPECS → DESIGN → TASKS — before or alongside writing implementation code, then keep those specs reconciled onto the code that actually shipped. The chain is not ceremony: each phase feeds the next, and the specs stay alive as versioned artifacts after launch.

## When to use

Reach for this when:

- You are starting a non-trivial feature, service, or project — anything beyond a one-file change.
- Docs and code have drifted, and you no longer trust the design docs to describe what runs.
- A workstream is large enough that "what it should do" and "how it does it" deserve separate scrutiny.

Red-flag thoughts that mean STOP and apply this skill:

- "I'll just start coding and write up the design after — I already know what to build."
- "The spec is basically right, no need to update it for this change."
- "What and how are the same thing here, one doc is enough."
- "We settled that in review already, but let me reopen it now that I'm building."
- "That open question is stale, I'll just delete it."

## The rule

1. **Write the chain in order, before implementation code.** Produce BRIEF (the problem and goal) → RESEARCH (what exists, constraints, options) → SPECS (the *what*: requirements, behaviors, acceptance criteria) → DESIGN (the *how*: architecture, mechanism, trade-offs) → TASKS (the implementation plan derived from SPECS + DESIGN). State explicitly how each phase consumes the one before it.
2. **Keep "what" and "how" in separate documents.** SPECS describe required behavior without prescribing mechanism; DESIGN commits to mechanism. TASKS is the build plan that falls out of both. Do not blur them into one file.
3. **Gate each phase behind an independent peer review.** Have a second agent or person review the doc, then record the verdict *in the doc itself* (e.g., "Status: Approved" or "ACCEPT-WITH-NOTES"). Carry the review notes forward into later phases as refinements — do not re-litigate settled points.
4. **Treat specs as durable, versioned artifacts.** When the implementation diverges from the spec, reconcile the spec *onto the delivered code* and bump its version (v0.3 → v0.4). The spec must describe what shipped, not what you once hoped to ship. This holds doubly for a spec you don't own: an upstream OpenAPI document or a vendor's API reference is a hypothesis, not a contract — when it disagrees with the running system, the system wins (see [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md)).
5. **Strike through resolved open items, don't delete them.** Leave the original line with a strikethrough and a pointer to where it was resolved, so the decision trail survives.
6. **Run each independent workstream through its own full cycle.** spec → plan → build → test against real infrastructure. When that infrastructure isn't available, mark those paths EXPLICITLY as untested in the spec (e.g., gated behind a "prod" extra, flagged "untested without live cloud access") rather than implying every workstream completed a clean real-test it didn't. Don't let one workstream's docs bleed into another's. When you fan those workstreams out to parallel write-capable agents, see [parallel-agent-fan-out](../parallel-agent-fan-out/SKILL.md) for keeping them from colliding.

## Why

Code written without a spec encodes decisions you never examined; the design doc you back-fill afterward just rationalizes whatever you happened to type. Separating *what* from *how* lets reviewers catch a wrong requirement before you've spent days building the right mechanism for it. Recording verdicts in the doc means a settled debate stays settled — re-opening it in the next phase burns time and erodes trust in the chain. And a spec that freezes at its original optimistic claims becomes a lie the moment code diverges: the next person reads it, believes it, and builds on a fiction. Reconciling the spec onto reality keeps the document worth reading, which is the only thing that keeps it being read.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent shipped to a cloud platform — the `docs/BRIEF.md` header literally carried its place in the chain: *"Status: Approved — feeds SPECS → DESIGN → TASKS → TDD build."* RESEARCH closed with a peer-review addendum (§12) whose verdict, *"ACCEPT-WITH-NOTES,"* was then *"carried into SPECS/DESIGN (they refine the design; they are not re-research)"* — the notes moved forward as refinements rather than being re-argued. After launch, when the build diverged from the plan, the team didn't abandon the docs: SPECS went to v0.4 and DESIGN to v1.4, *"reconciled to delivered code — HTTP API + observability un-deferred, decision thresholds now YAML-tunable."* The specs described what actually ran. You can apply all of this on any stack: name your phases, review each, version the specs, reconcile after divergence.

## Anti-patterns

- Writing code first and back-filling a design doc as decoration that nobody updates again.
- Leaving a spec frozen at its original optimistic claims after the implementation diverged.
- Collapsing "what" and "how" into one document so requirements and mechanism blur and reviewers can't isolate either.
- Re-debating settled review notes in the next phase instead of carrying them forward as refinements.

## Cross-links

- [surgical-changes-with-checkpoints](../surgical-changes-with-checkpoints/SKILL.md)
- [docs-as-deliverable](../docs-as-deliverable/SKILL.md)
- [grounded-verifiable-gates](../grounded-verifiable-gates/SKILL.md)
- [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md)
- [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md)
- [parallel-agent-fan-out](../parallel-agent-fan-out/SKILL.md)
