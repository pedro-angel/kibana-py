---
name: battle-testing-on-real-infra
description: Use when about to call any integration, deployment, or hard guarantee "done" — prove it live end-to-end and capture the run as evidence.
---

# Done Means Validated Live, End-to-End

Nothing involving an external system, a deployment, or a durability/resume guarantee is "done" until it has run against real infrastructure, end-to-end, with the result captured as evidence. Mocks prove your wiring; only a live run proves reality.

## When to use

Reach for this skill whenever you are about to mark complete: an integration with a third-party API or provider, a deployment to a real environment, or any hard guarantee (durability, idempotency, cross-process resume, exactly-once, failover).

Red-flag thoughts — if you catch yourself thinking any of these, STOP and apply this skill:

- "The mocks are green, so it works."
- "The design guarantees it survives a restart / the docs say the endpoint returns X."
- "It's basically the same as the path we already tested."
- "I'll write the live test later / it's too slow to run every time."
- "The SDK handles that for us." (Did you watch it handle it?)

## The rule

1. Re-assert "done" against live infra. Provision the real services (a real database, a real deployment target, a real provider account), run the real agent or code path end-to-end through them, then tear the services down. Treat provision → exercise → destroy as one atomic act.
2. Make live tests a first-class, separately-runnable gate, distinct from the fast unit run. Examples: a `live` test marker, a `make test-live` target, a tagged CI stage, or a dedicated script. The default suite stays fast; the live gate is explicit and on-demand.
3. Validate the hardest guarantee with its own dedicated live test — never a design assertion. If you claim cross-process resume, prove it: pause on one process/instance and resume on a brand-new one over the same real backing store. If you claim idempotency, replay the same request live and assert one effect.
4. Record each live run as a machine-readable evidence artifact. Pin the exact command, the backends/endpoints used, the deployed revision or commit id, and a per-resource pass/fail. A captured file (JSON/YAML/log) — not prose, not "I checked it."
5. Probe external assumptions against the real endpoint before trusting docs. Hit it once and record the actual HTTP status, the real licensing/feature flag, the true model or API id, the real default limits. Believe the probe over the documentation. Across a whole API surface this becomes a standing stance: the spec is a hypothesis, the running system is ground truth — implement what the server does, and record each divergence in the code the next caller reads, not a report that rots.
6. Let live findings drive engineering decisions. When the real provider exposes a mismatch, change the approach — reject an SDK that misbehaves, raise a token/timeout budget that the provider silently overruns, swap a backend that fails the durability test. The live run is allowed to overrule the plan.
7. Bind tested to shipped. Assert the built artifact's content digest that passed the live gate is the one that deploys — a source revision alone is not enough, because a build cache the step never invalidated serves different bytes for the same revision, so a green run blesses code that never reaches production. (When you deploy source directly from a fresh checkout with no build cache, the revision *is* the digest.) Record that id in the evidence artifact and re-check it at the deploy edge.
8. When a path's happy case needs infrastructure you don't have — an enrolled device, a paid account, a peered cluster — do not fall back to mocks and call it untested. Drive the real route against the live system and assert its *exact* semantic rejection: the specific error condition or message, not merely a status code, so a routing or payload-shape bug still fails the test. Rank every path into three tiers — happy-path proven live > route proven live via its semantic error > unit-only with the missing precondition named — and treat only the third tier as untested against reality. A skipped path that names no missing precondition is a hole pretending to be covered.
9. When the external system is a model, prove it against a real model. A small local model served over a standard HTTP model API gives a genuine end-to-end round-trip — real serialization, real streaming, real tool-call shape — with no cloud key or spend. Mocking the model only re-tests your own wiring; it cannot surface the response your prompt actually elicits.

## Why

Mocks encode your assumptions, so they can only ever confirm them. Real systems fail in ways you did not think to mock: a provider silently consumes a budget you assumed was yours, an endpoint returns a status the docs never list, a "durable" store loses a write across a process boundary, a deployment IAM permission propagates too slowly. Each of these passes every mock and breaks in production. The cost of skipping the live gate is paid later and larger — in an incident, a customer-visible data loss, or a wrong architectural commitment that is expensive to unwind. A captured evidence artifact also converts "trust me" into something a reviewer, a future you, or another agent can verify without rerunning anything.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent shipped to a cloud runtime — the riskiest claim was that a paused run could resume after the original process was gone. Rather than assert it from the checkpointer's design, a dedicated live test (`tests/live/test_checkpointer_live.py`) paused a run on one saver instance and resumed it on a brand-new saver pointed at the same real managed document database; the resume write surviving that process boundary is what proved the guarantee, and the run was captured as a machine-readable artifact — `docs/evidence/serverless-live.json` pins the test path, the managed document database, a per-resource PASS, and the teardown. Separately, probing the real model provider revealed that an output-token budget set to 2048 was being silently consumed by reasoning tokens before any answer was produced (the evaluation write-up) — a provider-specific defect no mock could reproduce. The live finding directly changed engineering: `max_output_tokens` was raised from 2048 to 8192. The portable lesson: pick your single hardest guarantee, build one live test that can only pass if it is actually true, run it against real backends, and keep the captured result.

A second build the pack draws on — a REST API client covering an external system's entire surface, verified against a containerized live server — reinforced the same rules at scale. Its published spec and the running server disagreed on roughly twenty points — for example, a method the spec typed as `GET` with a JSON body that the server served as `POST` multipart; a field the spec marked writable that the server refused to update; an endpoint whose documented request path the server rejected for another — and each was found by probing live, implemented as the server behaved, and recorded in the calling method's own code rather than a side report. Endpoints whose happy path needed infrastructure the rig lacked — an enrolled device, a paid account, a peer cluster — were still driven live and asserted against the server's exact rejection, so a routing typo could not pass as "skipped." The two model-backed features were round-tripped through a small local model behind a standard HTTP API rather than a mock. Same lesson, wider surface: the running system, not the document, is the authority, and "no infra" is a reason to assert the real error, not to stop testing.

> The only real way to know something works is to go live with it with a real test. Battle-test it.

## Anti-patterns

- Declaring a feature done on green mocks that only exercised wiring.
- Asserting a durability or resume guarantee from the design, with no live cross-instance test that could falsify it.
- Trusting integration docs over a real probe of the endpoint.
- Leaving the live-validation result as prose ("verified locally") instead of a captured evidence file pinning command, backends, and revision.
- Marking a path "skipped — needs infra" when you could have driven the real route and asserted the server's exact rejection.
- Coding to the spec when the running system does otherwise, and burying the divergence in a report instead of the code the next caller reads.
- Mocking the model in a model-backed feature and calling the feature tested.

## Related skills

- [../grounded-verifiable-gates/SKILL.md](../grounded-verifiable-gates/SKILL.md)
- [../honest-reframing-over-overclaiming/SKILL.md](../honest-reframing-over-overclaiming/SKILL.md)
- [../secrets-and-teardown-discipline/SKILL.md](../secrets-and-teardown-discipline/SKILL.md)
- [../reversible-by-default-confirm-consequential/SKILL.md](../reversible-by-default-confirm-consequential/SKILL.md)
- [../autonomous-self-improvement-loop-safety/SKILL.md](../autonomous-self-improvement-loop-safety/SKILL.md)
- [../parallel-agent-fan-out/SKILL.md](../parallel-agent-fan-out/SKILL.md)
