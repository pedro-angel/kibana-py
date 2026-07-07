---
name: reversible-by-default-confirm-consequential
description: Use when an agent or automation can touch external systems — stay read-only/reversible by default and gate consequential acts behind durable human approval.
---

# Reversible by Default, Durable Human Approval for Consequential Acts

Build the system so it cannot harm anything it does not own: read-only and reversible on every external system by default, with each consequential or outward-facing action paused for an authorized human's approval. The pause must be durable — persisted before you wait — so a stopped run survives restarts.

## When to use

Apply whenever an agent or automation can reach a system you do not fully control: ticketing, wikis, repos, email, payment APIs, production data, customer-facing surfaces. Apply the moment a workflow's output could become public, mutate shared state, or be hard to undo.

Red-flag thoughts that mean STOP and apply this skill:

- "It's just a small write, I'll add a flag to disable it later."
- "The model's draft looks good enough to publish automatically."
- "I'll hold the approval step in memory — the run won't last long enough to restart."
- "We say it's read-only; we don't need a test proving it."
- "Let the agent post it and we'll review afterward if something looks off."

## The rule

1. **Make read-only an architectural invariant, not a flag.** Confine the only write side-effect to your own artifact store (your DB, your bucket, your output dir). External adapters expose read operations only; there is no code path that mutates an external system, so there is nothing to "turn off."
2. **Pin the invariant with a regression test.** Drive every external adapter method through a fake/recording transport and assert the HTTP verb (or operation type) is GET/read-only across all of them. Convert "we never write" from a claim into a failing build when someone adds a write.
3. **Pause before any consequential action and wait for explicit human approval.** The agent proposes; an authorized human disposes. Never auto-publish, auto-merge, auto-send, or auto-mutate.
4. **Make the pause durable: persist before you wait.** Write the full report and the proposed action to the store BEFORE entering the wait state. A paused run must be reviewable and resumable even after a crash, deploy, or scale-to-zero — including from a fresh instance or a different browser.
5. **Keep run state in a durable checkpoint/state store (a "checkpointer"), not process memory.** So a service can pause, drop to zero, and resume on a new instance by rehydrating state from the store — without re-running the model or re-doing the work.
6. **Show the reviewer the real basis for the decision.** Surface the deterministic gate's grading — grounded, verifiable facts — not an invented confidence score. The human approves on what actually routed the run.
7. **Enforce the posture in infrastructure too.** Private ingress, no public binding, read-only egress credentials. The principle should hold even if application code is wrong.

## Why

Reversibility is your blast-radius control. If the agent can only read external systems and only writes to its own store, the worst failure is a bad draft sitting in your DB — not a corrupted ticket, a wrong email blast, or a force-pushed branch. A human-approval gate converts the agent from an autonomous actor into a proposer, which is the only safe posture when actions are public or hard to undo.

Durability is what makes the gate real. An in-memory pause is a promise that survives only until the next deploy, OOM, or autoscaler event — and consequential runs are exactly the ones you cannot afford to silently drop or blindly re-run. Persisting before waiting means a paused decision is a durable, auditable object, not a thread you are praying stays alive. And a test pinning read-only access is what keeps the invariant true six months and twenty commits later, when the original author is gone and "just one write" looks harmless.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent that drafts documentation from a ticketing system and was shipped to a cloud runtime — the safety posture was enforced at three layers:

- A recording-transport test (`test_ticketing_adapter`) exercised every adapter method and asserted `set(seen) == {"GET"}` — proving nothing but reads ever reached the external SaaS. Adding a write breaks the build.
- The graph's human-in-the-loop interrupt persisted the report and proposal to the store *before* pausing, with the explicit intent that a reviewer could resume "from a fresh page (or a different browser) without re-evaluating."
- The deployment relied on the orchestrator persisting full run state, so a later `resume` call rehydrated and continued "even on a fresh instance after scale-to-zero" (DEPLOYMENT docs §4), backed by private ingress and read-only egress credentials.

You can apply the same shape without knowing that project: read-only external adapters, a test that pins it, persist-then-pause for approval, checkpointed state, and infra that assumes the code might be wrong.

## Anti-patterns

- Holding the approval pause in process memory, so a restart kills it and forces a full re-run (or silently drops the decision).
- Treating read-only as a feature flag that can be flipped, rather than an invariant with no write path to flip.
- Auto-publishing the AI draft instead of waiting for explicit human approval.
- Claiming "never writes to external systems" with no test pinning GET-only / read-only access.

---

Related skills:

- [../battle-testing-on-real-infra/SKILL.md](../battle-testing-on-real-infra/SKILL.md)
- [../grounded-verifiable-gates/SKILL.md](../grounded-verifiable-gates/SKILL.md)
- [../secrets-and-teardown-discipline/SKILL.md](../secrets-and-teardown-discipline/SKILL.md)
- [../hexagonal-with-enforced-contracts/SKILL.md](../hexagonal-with-enforced-contracts/SKILL.md)
- [../structural-security-boundary/SKILL.md](../structural-security-boundary/SKILL.md)
- [../autonomous-self-improvement-loop-safety/SKILL.md](../autonomous-self-improvement-loop-safety/SKILL.md)
