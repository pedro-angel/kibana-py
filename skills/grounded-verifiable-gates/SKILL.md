---
name: grounded-verifiable-gates
description: Use when an LLM or agent emits decisions or claims and you need to turn fuzzy output into a verifiable, regression-protected signal.
---

# Make AI Output Verifiable: Grounding + Deterministic Gates + Eval Harness

Never let a model's self-assessment be the decision. Force every claim to cite source text that literally matches, compute the outcome with a pure tested function over only the grounded claims, and protect that function with an eval harness that runs the real production path and fails CI on regression.

## When to use

Reach for this whenever a model's output influences what happens next: a judge that approves or flags, an extractor that fills a record, a classifier that routes, an agent that decides to act. The higher the cost of a wrong, confidently-stated answer, the more this applies.

Red-flag thoughts that mean STOP and apply this skill:

- "The model rated it 0.9, so we'll pass it." — a self-rating is not a verdict.
- "It cited a source, so it must be grounded." — citing is not matching; check the quote against the text.
- "We'll eval against a simplified harness / a copy of the prompt." — then you're measuring a thing you don't ship.
- "The thresholds feel about right." — feelings are not calibration.
- "Precision looks great" (where the same model graded itself) — that number is circular.

## The rule

1. **Demand a verifiable citation per claim.** Require each finding to carry a quote, and verify that quote is a literal substring of its cited source after normalizing both through one shared text pipeline (same Unicode form, whitespace, casing rules). A quote that does not match is marked `ungrounded`.
2. **Drop ungrounded claims before they can matter.** The decision function reads only grounded findings. By construction, a hallucinated quote cannot move the outcome — there is no path from an unmatched claim to a verdict.
3. **Make the verdict a pure function.** Compute the outcome deterministically from the grounded findings against pinned default thresholds. Unit-test it in isolation. The model proposes findings; code decides.
4. **Drive production and review from the same gate.** The routing edge in production and any human-review UI must call the identical gate. Reviewers see exactly the signal that routed the run — no parallel logic, no drift.
5. **Build the eval harness on the real path.** The harness must invoke the unchanged production use-case and the same decide gate, and feed fixtures through the same text pipeline. It measures the judge you ship, not a re-implementation of it.
6. **Turn metrics into a CI pass/fail.** Pin gates in version control as tunable config and exit non-zero on breach. Favor judge-independent gates: recall (did it catch real issues), grounding rate (are claims verifiable), over-flag rate (does it cry wolf on good inputs). Example defaults: `min_recall 0.70`, `max_over_flag 1.0`, `min_grounding 0.80`.
7. **Calibrate, then prove discrimination.** Set thresholds from a real run with documented provenance (which model, which inputs, when). Prove the gates actually separate quality: a strong model clears them; a deliberately weaker one fails. A gate everything passes is decoration.
8. **Report honestly.** Headline the judge-independent metrics. Report judge-dependent ones (e.g. precision, when the model grades its own work) as bounds, and disclose the self-judging bias explicitly.
9. **Verify an agent's "done" by mechanism, not by its word.** When an agent reports it performed an action, confirm it from the world — the file's new content, the record's existence, a zero exit code — and fail closed when the check cannot confirm. A worker that says "done" having written nothing must read as nothing-happened, not as success; its self-report is a proposal, and the mechanical check is the verdict.
10. **Test the deny path, and mutation-verify the fail-closed default.** A gate or guard's whole purpose is its deny/fail branch — yet that is the branch left untested, because triggering it needs a violation the clean run never produces, so the tests assert "passes clean" and the behaviour *on failure* is never checked. Drive the guard to DENY and assert the deny signal itself — the exit code, the decision, the raised error — not merely that the allowed case passes. Then prove it fails closed by **mutating the fail-closed return**: flip it and re-run; if the suite still passes, the guarantee is untested. A claimed safety property ("fails closed") must be enforced and tested on *every* path, not asserted in a comment.

## Why

An LLM's stated confidence and its actual correctness are only loosely correlated, and a fluent wrong answer is more dangerous than an obviously broken one. If the model's own number is the gate, a hallucination flows straight to the outcome and you have no tripwire. Grounding gives you a mechanical filter — unverifiable claims are inert. A pure verdict function gives you something you can unit-test and reason about. An eval harness on the real path gives you regression protection that actually reflects production; one on a re-implementation gives you false comfort that breaks silently when the prompt or pipeline drifts. And calibrated, version-controlled gates convert "it seemed fine in the demo" into a signal that blocks a merge. Skip these and quality becomes invisible until a user hits the failure — at which point you're debugging vibes, not a contract.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent (an LLM judge reviewing documentation, shipped to a cloud runtime) — `docs/ARCHITECTURE.md` states: *"A finding whose quote is not literally present — a hallucination — is marked ungrounded and is ignored by the decision gate …"* (the source continues "… and excluded from the proposal prompt"). The eval harness was built to reuse the production evaluation entrypoint and the domain `decide` gate unchanged, so, per `docs/EVALUATION.md`, *"it measures exactly the judge the agent runs in production"* — fixtures normalized through the same text pipeline as live input. The CI gates lived in `evals/golden/labels.yaml` beside the golden labels as config: `min_recall_deterministic: 0.70`, `max_over_flag_good: 1.0`, `min_grounding_rate: 0.80`, and the run exited non-zero on breach. Crucially, the team reframed precision honestly: because the model graded its own output, precision was reported as a bound with the bias disclosed, while recall and grounding — independent of the judge's self-opinion — carried the headline. You can apply all of this without knowing that project: substring-check quotes, gate on grounded findings only, eval the real code path, pin thresholds in CI, calibrate against a labeled run, and be honest about which numbers the model could game.

## Anti-patterns

- Letting the LLM's own verdict or score be the decision, instead of a deterministic function of grounded findings.
- Scoring a parallel re-implementation (a copied prompt, a simplified scorer) rather than the actual production path, so eval numbers don't reflect what ships.
- Setting gate thresholds by intuition instead of calibrating against measured behavior — and never checking that a weaker model would fail them.
- Presenting a self-judged precision as the headline metric while hiding that the model graded its own work.

## Enforcement

This skill's harness is its own enforcement: a CI job that runs the deterministic gate over the fixed corpus on every change and fails on regression. What a machine additionally holds: grounding invariants as assertions (every cited id exists, every span matches its source), thresholds living in config so a calibration change is a reviewable diff, and fail-closed semantics — an empty corpus or a skipped eval job is a FAIL, never a quiet green. A gate's own deny/fail branch carries its own regression test, mutation-checked — flip the fail-closed return and the suite must go red; a still-green suite means the deny path is unguarded and can silently regress to fail-open.

## Related

- [../honest-reframing-over-overclaiming/SKILL.md](../honest-reframing-over-overclaiming/SKILL.md)
- [../battle-testing-on-real-infra/SKILL.md](../battle-testing-on-real-infra/SKILL.md)
- [../hexagonal-with-enforced-contracts/SKILL.md](../hexagonal-with-enforced-contracts/SKILL.md)
- [../reversible-by-default-confirm-consequential/SKILL.md](../reversible-by-default-confirm-consequential/SKILL.md)
- [../autonomous-self-improvement-loop-safety/SKILL.md](../autonomous-self-improvement-loop-safety/SKILL.md)
