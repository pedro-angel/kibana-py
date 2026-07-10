---
name: definition-of-done-tooling
description: Use when about to claim work is complete, shippable, or ready to release or tag a milestone — run a script that reads declared criteria and emits GO/NO-GO instead of asserting completion from memory; the author never self-certifies.
---

# A Script Certifies Done, Not the Author's Memory

A definition of done that lives as a checklist in someone's head, or a paragraph in a PR template, decays over a long session — steps get skipped under time pressure, and the person who wrote the code is the worst-positioned person to judge whether they finished it. Make completion a mechanical gate: a script reads a small declared list of criteria, runs every one marked required, and emits a single GO or NO-GO. The author's belief that they're done is a proposal; the script's exit code is the verdict.

## When to use

Before claiming any non-trivial unit of work is complete, before cutting a release or tagging a milestone, and before a PR description says "ready for review" or "ready to merge."

Red-flag thoughts that mean STOP and apply this skill:

- "I've mentally checked everything off, we're good." (Mental checklists decay; a script doesn't.)
- "Tests pass, that's the definition of done here." (Is that written down anywhere, or is it just what you remember today?)
- "This criterion doesn't really apply, I'll just skip it." (Skipping is a silent deletion; the gate needs a visible `n/a`, not silence.)
- "I'll edit the config so it passes." (You're editing the exam, not passing it.)
- "Close enough — most of it's green." (One required NO-GO fails the whole gate, by design.)

## The rule

1. **Declare every completion criterion in a small config, one line per criterion, each marked `required` or `n/a`** — never left implicit. Typical criteria: tests/CI green, no leftover placeholders in shipped artifacts, docs current, acceptance tests green, lint, coverage threshold, telemetry wired.
2. **Back every `required` criterion with a real, runnable check.** A criterion with no check behind it — a vague "where applicable" — is not a gate, it's a comment; either wire a check or mark the criterion `n/a`.
3. **Make `n/a` a visible, reviewable decision, not an absence.** Deleting a line hides that anyone considered the criterion; marking it `n/a` in the config leaves a reviewer the chance to disagree with the call.
4. **Run every `required` check through one script that emits a single GO or NO-GO** — never a partial pass. Any required NO-GO fails the whole gate; there is no "mostly done."
5. **On NO-GO, fix the failing criterion and re-run the whole gate.** Never edit the config to make a failing check pass or disappear — that is certifying the exam, not the work.
6. **Wrap the project's existing CI/test entrypoints rather than re-implementing them inline**, so the gate stays fast, carries no separate credential surface, and can't silently drift from what CI actually runs.
7. **Never let the artifact's author mark it done from memory.** The script's output is the completion claim; a person or PR description asserting "done" without having run it is asserting nothing.

## Why

Self-certification fails for the same reason self-review fails: the person closest to the work has the least ability to see what they missed, and under time pressure the checklist in their head quietly shrinks to whatever they remember without prompting. A script has no such pressure and no stake in the outcome — it either observed the criterion pass or it didn't. Requiring a visible `n/a` rather than allowing silent omission is what keeps the config honest over time: a criterion nobody explicitly excused can't be waved away by whoever's in a hurry this week. And wrapping the existing CI entrypoint rather than duplicating its logic is what keeps the gate from becoming a second, drifting definition of "passing" that quietly diverges from the one CI actually enforces.

## In practice

Adapted from cmanaha/extended-superpowers (MIT), rewritten here without any reference to a specific hook mechanism or plugin runtime — the gate is any script your project can run, wired into whatever pre-merge or pre-release checkpoint your team already has. A minimal reference implementation of this exact pattern lives in the `kibana-mcp` project: a `dod.config` file declares each criterion `required` or `n/a`, and `scripts/checks/definition-of-done.sh` reads that config, runs every required check, and prints a single GO/NO-GO verdict, wrapping the project's own CI entrypoint rather than re-implementing it. It is named here only as a concrete shape worth looking at, not vendored into this pack — the pattern itself is language- and tool-agnostic: the same three moves (declare, gate, wrap-don't-duplicate) work equally as a POSIX-sh script, a Makefile target, or a CI job step in any stack.

## Anti-patterns

- Claiming "done" or "shipped" without running the gate.
- Marking a criterion `required` with no real check wired behind it.
- Editing the config to force a pass instead of fixing the underlying failure.
- Silently deleting a criterion instead of marking it `n/a`.
- Letting the gate re-implement CI inline instead of wrapping the existing entrypoint, so the two drift apart.
- The artifact's own author asserting "done" without having run the script.

## Enforcement

This skill is the enforcement shape the others plug into, and it is machine-checkable by construction: criteria declared one per line as `required` or `n/a`, every `required` backed by a runnable command, one script emitting a single GO/NO-GO, wrapping the CI entrypoints it certifies rather than re-implementing them. Guard the gate itself: the config is reviewed like code — editing the exam is the named anti-pattern — and a meta-check asserts that no `required` criterion points at nothing.

## Related skills

- [acceptance-tests-observable-outcomes](../acceptance-tests-observable-outcomes/SKILL.md)
- [grounded-verifiable-gates](../grounded-verifiable-gates/SKILL.md)
- [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md)
- [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md)
