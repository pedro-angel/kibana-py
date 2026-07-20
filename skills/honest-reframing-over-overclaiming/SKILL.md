---
name: honest-reframing-over-overclaiming
description: Use when a live result contradicts the hoped-for story or a metric could be gamed — state what really works and never fake a green.
---

# Reframe to Measured Reality, Never Fake a Pass

When results contradict the claim you wanted to make, rewrite the claim to match the measurement — carrying the exact numbers — instead of bending tests, fixtures, or ground truth until the metric turns green.

## When to use

- A live run, benchmark, or eval disagrees with what the design or spec promised.
- A metric is about to go green and you are tempted to adjust the corpus, threshold, or labels to get it there.
- You are about to call something "proven," "working," or "validated."
- You are reporting a number and choosing which number to lead with.

Red-flag thoughts — if you catch yourself thinking any of these, STOP and apply this skill:

- "I'll just tweak the fixture / threshold so it passes."
- "This one case is mislabeled, I'll relabel it as a false positive and move on."
- "The focused slice looks great — I'll report that and skip the broader run."
- "It worked once, so it works."
- "I already fixed the client-facing doc; the original spec doesn't matter."
- "Close enough — I'll call it done and note the caveat later (i.e. never)."

## The rule

1. **Rewrite the claim, not the corpus.** When a live result contradicts a design claim, change the claim to measured reality with the exact numbers — say "ranked below the intended #1," not "ranks #1," and only cite a rank you actually measured. Treat that gap as motivation for a stronger fix, not something to paper over.
2. **Propagate the correction everywhere it appeared.** Fix the client-facing doc AND the original design spec, and cross-link them. Leave no stale optimistic claim behind in any artifact.
3. **Never touch ground truth to win.** Keep fixtures and tests fixed. If changing them seems necessary, stop and get explicit agreement first — "don't change fixtures, let's talk about it" is the default posture.
4. **Keep a balanced corpus.** Maintain good AND bad cases: true negatives, over-flag stressors, and planted-issue positives. A detector that flags everything must still fail your suite.
5. **Log label debt; never silently score it.** When a run surfaces a real but unlabeled finding, record it as label debt that grows the golden set — do not quietly count it as a false positive or a pass.
6. **Defer honestly.** Mark unfinished work "deferred" with the exact missing precondition. Give limitations their own section. Scope precisely what "proven" means — an existence proof on one case is not statistical robustness.
7. **Let measurement override intuition.** When the harness shows an idea regresses — yours or the user's — kill it. The number wins.
8. **Pin the honest residual as a passing-by-design test.** When you defer or label a known gap (rule 6), encode the *specific* documented property as a test that passes by design and asserts the limitation still holds — so a change that alters that property trips the suite instead of silently rewriting the claim. This machine-checks the pinned technical fact, not the surrounding prose: it catches the gap being closed or changed, not a stale sentence nobody updated — so still propagate the claim (rule 2).

## Why

An overclaim that survives into the next phase becomes the foundation someone else builds on; the cost compounds. A faked green hides exactly the failure the test existed to catch, so the bug ships anyway — now with a passing suite vouching for it. Tuning fixtures to the current model destroys the corpus's ability to detect the next regression. The honest number, stated once with its caveats, is cheaper than the silent debt of a story that was never true. Reframing also redirects energy productively: a precise "it ranks #3" points straight at the retrieval phase to strengthen, where "it works" pointed nowhere.

## In practice

On the project this was distilled from — a human-in-the-loop AI agent — the design assumed an in-process embedding step would surface the correct reference article as the top hit. A single live run showed it did not rank the intended article #1. The honest move was taken twice: the result was written up as measured reality ("these motivate a stronger retrieval phase rather than being rescued by the current [approach]" — the bracket marks a substitution; the source string says "the current RAG"), and the correction was pushed into BOTH the user-facing evaluation doc and the original design spec, cross-linked. Separately, when an eval produced a flattering focused-slice score, the write-up reported the broader whole-corpus figure as the headline (0.90 across 20 cases) and named the specific under-escalating cases as concrete tuning targets — rather than leading with the better-looking slice. And when someone reached for the fixtures to get a metric green, the standing rule held: "Don't change fixtures, let's talk about it first." You can apply all three without knowing anything else about that project: correct the claim, correct it everywhere, and freeze ground truth.

## Anti-patterns

- Tuning the fixture corpus or relabeling cases to flip a red metric green.
- Correcting the client-facing doc but leaving the original design spec still overclaiming.
- Leading with the flattering focused-slice number while hiding the broader, worse result.
- Presenting a single live call as statistical proof of robustness.
- Leaving a known limitation as prose only, so it silently rots — or is quietly "fixed" without anyone noticing the documented claim changed.

## Enforcement

What a machine can check: the temptation paths. Ground-truth fixtures behind required review (a CODEOWNERS rule or protected path), so no fix can silently edit the exam; a corpus-balance check that fails when the good or bad case count drops to zero; numbers in shipped claims traced to generated artifacts rather than hand-typed prose ([docs-as-deliverable](../docs-as-deliverable/SKILL.md)). The reframing itself is judgment — the machine's job is making the dishonest path loud, not choosing the honest words.

---

Related skills:

- [grounded-verifiable-gates](../grounded-verifiable-gates/SKILL.md)
- [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md)
- [docs-as-deliverable](../docs-as-deliverable/SKILL.md)
- [spec-driven-development](../spec-driven-development/SKILL.md)
- [structural-security-boundary](../structural-security-boundary/SKILL.md)
- [autonomous-self-improvement-loop-safety](../autonomous-self-improvement-loop-safety/SKILL.md)
- [evidence-over-deference](../evidence-over-deference/SKILL.md)
