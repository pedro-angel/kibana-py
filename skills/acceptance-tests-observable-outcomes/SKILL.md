---
name: acceptance-tests-observable-outcomes
description: Use when you need to prove a feature actually delivers its intended outcome to a user or caller, not just that its code paths run — write executable acceptance tests against real, observable outcomes, derived from the spec before or independent of the implementation.
---

# Acceptance Tests Assert What the User Sees

Unit and integration tests answer "did we build it right" — they assert code paths ran. Acceptance tests answer "did we build the right thing" — they assert what a user or caller actually observes on the real system. Only the second catches a feature that was fully specified, fully coded, and never actually wired to anything a user can reach.

## When to use

Whenever a spec's success criteria describe an observable outcome — a value on screen, a header in a response, a file left on disk, a specific error message — and before claiming that feature, or any piece of automation, is done. Reach for it any time you're tempted to answer "does it work" by re-reading the code that's supposed to make it work, instead of watching it work.

Red-flag thoughts that mean STOP and apply this skill:

- "The unit tests are green, so the feature works." (Green units prove the pieces; they don't prove the pieces are wired together for the user.)
- "I traced the code path by eye, it clearly returns the right value." (A trace is not an execution.)
- "The mock returns what production would return." (Then you've tested the mock, not the outcome.)
- "It passed once, that's enough — this isn't safety-critical." (One green run on a non-deterministic path is luck, not proof.)
- "Cleanup only matters if the test passes." (A failing run that skips teardown leaves debris the next run inherits.)

## The rule

1. **Derive each acceptance test from an observable success criterion in the spec** — what a user sees, what a caller receives, what artifact exists — never from an internal function's return value. If the spec says "the response includes field `X`," the test asserts that field's presence in the real response; it does not assert that some internal serializer function was called with the right arguments.
2. **Write the test before or independent of the implementation**, from the spec alone. A test written by reading the implementation encodes the implementation's bugs as its own expectations.
3. **Run it against the real system a user actually hits** — the deployed service, the real CLI invocation, the actual file the process writes — not a stand-in that only proves your own wiring. Where a live system is genuinely unavailable, drive the real route anyway and assert the exact semantic rejection rather than quietly falling back to a mock (see [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md)).
4. **Assert the semantic essentials, not incidental normalization.** Match the meaningful content — the value, the status, the substring that matters — and tolerate formatting the spec never promised (whitespace, key order, timestamp precision). An over-tight assertion turns a harmless refactor into a false failure and teaches the team to stop trusting red.
5. **Clean up unconditionally.** Teardown of anything the test created runs whether the assertions passed or failed — a guaranteed-to-run block, not a step that executes only on the happy path. A test that leaves debris on failure corrupts the next run's baseline.
6. **Run more than once when timing, retries, or model output are involved.** A single pass on a non-deterministic path is an anecdote, not proof; use a threshold across repeated runs instead of trusting one green.
7. **Treat a red or missing acceptance test as the real "not done yet" signal.** A green unit suite does not license marking the feature complete while the acceptance test is still red, or not written.

## Why

The gap this closes is specific and common: every internal function tested in isolation can be correct, and the feature can still be unreachable — an event never wired to its handler, a route never mounted, a config flag never read. Only an assertion made against what the user actually experiences catches that gap, because it exercises the seam between the pieces, not the pieces themselves. Matching on semantic essentials rather than incidental output keeps the suite honest in both directions: too loose and it stops catching real regressions, too tight and every unrelated refactor turns it red until the team learns to ignore failures — which is the same trust collapse either way. And unconditional cleanup exists because the moment you make teardown conditional on success, the first failure becomes the seed of every failure after it.

## In practice

Adapted from cmanaha/extended-superpowers (MIT), rewritten here as a general test-writing discipline with no tie to any specific test runner, plugin format, or bundled evaluation tooling. A representative example, genericized: a spec states that a status indicator must display the literal string `ctx 127K (63%)`. The acceptance test asserts that exact string is present in the real rendered output the user would see — it does not assert that an internal `format_context_usage()` helper returns the tuple `(127000, 0.63)`, because a helper can return the right tuple while the rendering layer that's supposed to consume it is never called. The failure the acceptance test catches — and the unit test cannot — is precisely that disconnection.

## Anti-patterns

- Asserting an internal function's return value and calling it acceptance.
- Deriving the test by reading the implementation instead of the spec.
- Over-matching incidental formatting so a harmless refactor turns the suite red.
- Skipping cleanup on a failing-assertion path, so a red run poisons the next one.
- Trusting a single non-deterministic pass as proof.
- Claiming "done" with the acceptance test still unwritten or still red.

## Enforcement

What a machine can check: that the suite exists, runs against the real surface, and cleans up. A named acceptance stage separate from the unit run, failing closed when zero acceptance tests are collected; unconditional teardown proven by a deliberately-failing test that still leaves the substrate clean; repeat-run thresholds encoded in the runner for non-deterministic paths. Whether an assertion matches the spec's observable criterion is judgment — reviewable because each test names the criterion it asserts.

## Related skills

- [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md)
- [definition-of-done-tooling](../definition-of-done-tooling/SKILL.md)
- [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md)
- [spec-driven-development](../spec-driven-development/SKILL.md)
