---
name: adversarial-lens-review
description: Use when a spec, plan, or implementation must be independently reviewed before it is trusted, committed, or advanced to the next phase — dispatch a fresh reviewer per named lens whose job is to refute the artifact, not confirm it.
---

# Refute, Don't Confirm: Adversarial Review by Named Lens

Cooperative review confirms what the author already believes; adversarial review tries to break it. An author who reviews their own work grades against their own blind spots — everything looks compliant because they wrote it to look compliant. The fix is structural, not attitudinal: put the artifact in front of a reviewer with no context from writing it, whose only job is to find what's wrong, through a specific named lens.

## When to use

At the spec-to-plan, plan-to-code, and code-to-merge gates — anywhere an artifact needs to be trusted before the next hard-to-reverse step. This hardens the "gate each phase behind review" step of [spec-driven-development](../spec-driven-development/SKILL.md) into a concrete, binding protocol.

Red-flag thoughts that mean STOP and apply this skill:

- "I re-read it myself and it looks solid." (You wrote it to look solid to you.)
- "One reviewer said it looks good, that's enough." (A single "looks good" is cooperative, not adversarial.)
- "The reviewer fixed the two issues they found, we're done." (Reviewers enumerate; they don't fix — a reviewer that fixes has stopped finding.)
- "It passed the code-quality pass, ship it." (Did it pass spec-compliance first? The two catch different bug classes.)
- "That constant is obviously fine." (Every bare number needs a justification a lens can check.)

## The lens contract (binding — dispatch the full row for the artifact)

| Artifact | Named lenses (one fresh reviewer each) |
| --- | --- |
| spec | factual-grounding, completeness, design-flaw/race-condition, testability |
| plan | spec-coverage, testing-and-trackability, sequencing-and-anti-hubris |
| implementation | spec-compliance, THEN code-quality |

For implementation, run spec-compliance first, then code-quality — they catch different bugs: compliance asks "did you build what was specified," quality asks "did you build it correctly." Running them out of order lets a style fix quietly bless a missed requirement. The sequencing-and-anti-hubris lens enforces that every bare constant or threshold in a plan carries its selection logic — "why 7 retries, not 3" — not just a number that felt right.

## The rule

1. **Identify the artifact type and dispatch its full lens row** — never a single generic reviewer standing in for the set.
2. **Give each lens a fresh reviewer with no authorship context** — a separate session, a different reviewing agent or person, ideally a different underlying model than whatever produced the artifact. Sunk cost in the work disqualifies a reviewer.
3. **Instruct every reviewer to enumerate, not fix**, and to default to finding problems rather than confirming intent.
4. **Require severity-graded findings in one shape**: `[BLOCKER|MAJOR|MINOR] <location> — <problem> → <suggested fix>`, plus a one-line verdict per reviewer. This is what makes findings actionable and comparable across review rounds.
5. **Run every lens in the row in parallel** where your setup allows it, so one artifact gets the full row's worth of scrutiny in one pass.
6. **Loop until clean.** The author fixes; re-dispatch only the lenses that found something; repeat. Neither a BLOCKER nor a MAJOR gets waved through as "close enough."
7. **Keep MINORs on the record with an explicit disposition** — fixed, deferred, or won't-fix-because-X — instead of silently dropping them between rounds.

## Why

A reviewer who wrote the artifact cannot see past their own framing — they will re-derive the same reasoning that produced the artifact and confirm it, because that reasoning is invisible to them as a choice. A fresh reviewer with a named lens has no such blind spot for that specific failure class, because the lens is the only thing they were asked to look for. Splitting the row into named lenses also guarantees coverage that a single "does this look right" pass reliably misses: a reviewer asked generically to review a plan will gravitate to whatever catches their eye, not systematically to sequencing, coverage, and trackability in turn. Severity grading turns a wall of comments into a triage list, and the re-review loop is what catches the possibility that a fix for one finding introduced another.

## In practice

Adapted from cmanaha/extended-superpowers (MIT) and rewritten here as an agent-agnostic protocol: any reviewer capable of reading the artifact and returning severity-graded findings can fill a lens — a separate agent session, a different model, or a human colleague — with no reference to a specific hook mechanism, marketplace, or bundled reviewer agent. On a migration plan, a sequencing-and-anti-hubris pass once caught a hard-coded `retry_count = 7` with no comment explaining the choice; the fix wasn't a different number, it was one line tying the count to the provider's documented rate-limit window. On a spec, a design-flaw lens found that two of the plan's steps both wrote the same record with no ordering guarantee between them — a race the author hadn't seen, because while writing the doc they'd mentally serialized the two writes without realizing nothing in the system actually enforced that order. Neither finding would have surfaced from one reviewer skimming for "does this look right"; each came from a lens whose only job was that specific failure class.

## Anti-patterns

- The author self-reviewing, or a single generic reviewer standing in for the full lens row.
- A reviewer that edits the artifact instead of enumerating findings.
- "Looks good" verdicts with no attempt to refute.
- Skipping the re-review loop after a fix, so the fix itself ships unreviewed.
- Running code-quality review before spec-compliance is clean.
- A bare constant or threshold surviving the sequencing-and-anti-hubris lens with no stated reasoning.

## Enforcement

What a machine can check: the protocol, not the insight. Phase advancement blocked while any BLOCKER or MAJOR lacks a recorded resolution; findings parseable in the one severity-graded shape, with MINORs carried forward under explicit dispositions; and in agent setups the dispatch itself — one fresh reviewer per lens in the artifact's row, spec-compliance strictly before code-quality. The quality of a refutation is judgment; the completeness of the row is not.

## Related skills

- [spec-driven-development](../spec-driven-development/SKILL.md)
- [grounded-verifiable-gates](../grounded-verifiable-gates/SKILL.md)
- [evidence-over-deference](../evidence-over-deference/SKILL.md)
- [environment-research](../environment-research/SKILL.md)
