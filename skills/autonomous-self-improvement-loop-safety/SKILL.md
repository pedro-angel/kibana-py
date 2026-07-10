---
name: autonomous-self-improvement-loop-safety
description: Use when building automation that edits, tests, or deploys itself — an agent that regenerates its own code, a self-updating pipeline, any loop that modifies the thing running it.
---

# Automation That Changes Itself Needs an Adversary, a Disposable Workspace, and a Human on the Merge

When a loop generates changes to its own codebase, the ordinary gate is necessary but not sufficient: it edits the thing that edits, so a bug compounds and a confused or compromised worker can rewrite its own guards. Contain each cycle in a throwaway workspace, decide success by mechanism rather than the worker's word, bind what you tested to what you ship, keep an adversary looking for what the gate cannot see, and keep a human on the irreversible step.

## When to use

Reach for this whenever automation acts on its own substrate: an agent that proposes edits to the repository it runs from, a self-updating deployment, a code-generation worker whose output is committed, any loop where the output modifies the next run's behavior.

Red-flag thoughts — if you catch yourself thinking any of these, STOP and apply this skill:

- "The worker said it made the change, so it did."
- "The gate is green, so the change is correct."
- "It edits the repo in place — cloning fresh each time is wasteful."
- "We tested the branch; deploying from the cache is the same bytes."
- "The prompt tells the worker not to touch the guards, so it won't."
- "It can open the merge itself — a human reviewing every one is slow."

## The rule

1. **Run each cycle in a disposable, freshly-cloned workspace** with its own isolated, throwaway configuration, and destroy it at the end. Never let the loop edit its own running tree — a bad cycle must cost nothing and touch nothing live.
2. **Decide success by mechanism, not by the worker's claim.** The authoritative signal that a change happened is a deterministic check of the workspace (version-control status, a real diff) — never the worker's own "done." A run that wrote nothing is a clean no-go, never an empty or hallucinated result. (→ [grounded-verifiable-gates](../grounded-verifiable-gates/SKILL.md))
3. **Bind tested == shipped.** The exact artifact that passed the gate — its content digest, or the source revision when you deploy from a fresh checkout with no build cache — must be the one deployed or proposed. A self-modifying loop is especially prone to shipping from a stale cache it never invalidated. (→ [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md))
4. **Keep a recurring adversarial self-review that assumes the gate is blind.** For every change that touches a trust boundary, run an independent pass whose job is to *refute* it — to find the identity forge, the fail-open alias, the ordering bug that only appears under real execution. The gate proves the build runs; the adversary raises confidence by trying and failing to break it, surfacing what a green suite structurally cannot see. Run it every time; it earns its keep on the bugs the gate is blind to.
5. **Stay propose-only on anything consequential.** The loop opens a reviewable proposal; a separate authority — a human, or a credential that structurally cannot merge — lands it. The generation path never reaches the protected branch on its own. (→ [reversible-by-default-confirm-consequential](../reversible-by-default-confirm-consequential/SKILL.md))
6. **Sandbox the write-capable worker structurally, not by prompt.** A worker holding write/exec tools runs under a real isolation boundary — a separate identity it cannot escape. The disposable checkout of rule 1 bounds *accidental* self-corruption; it is not containment (a same-identity worker can write outside it), so the boundary against a *compromised* worker is the identity/OS mechanism, never the directory. (→ [structural-security-boundary](../structural-security-boundary/SKILL.md))
7. **Label every step real or mock, and fail closed on mock.** A cycle step backed by a fake is UNVERIFIED and must not count toward green; a single unverifiable required step sinks the whole run. (→ [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md))

## Why

Self-modifying automation is uniquely dangerous because the artifact under change is also the machinery doing the changing: a defect does not just ship, it can disable the very check that would have caught it, and a subverted worker can rewrite its own constraints. The deterministic gate is real protection but structurally blind to a class of failures — a privilege forged through an identity reset, a deny-list slipped by an alias, a bug that only manifests under real execution — that only an adversary or a live run exposes. Disposable isolation makes a bad cycle free. The mechanical empty-check turns a lazy or hallucinating worker into a clean no-go instead of an empty proposal. The tested==shipped bind makes "we tested it" mean "we tested exactly this." And the human (or unmergeable credential) on the merge keeps a person on the 1% that is expensive to undo.

## In practice

Picture an autonomous agent that proposes improvements to its own codebase. Each cycle clones the repo into a throwaway directory with its own isolated config, runs a real write-capable worker to make the change, and then decides "did anything change?" from version-control status — not the worker's summary — so a run that wrote nothing is a clean no-go rather than an empty proposal. The revision that passed the gate is the same one it opens the proposal from; a mismatch aborts first. A separate adversarial pass reviews every change that touches a trust boundary — it exists because a green gate is structurally blind to a class of defects (a forged privilege, a guard bypassed by an aliased argument, a bug that only surfaces under real execution) that a passing suite cannot see. The credential that opens the proposal cannot merge it; a human does. None of this depends on a particular language or runtime: clone fresh, verify by mechanism not by claim, bind tested to shipped, keep an adversary and a human in the loop.

## Anti-patterns

- Letting the loop edit its own running workspace, so a bad cycle corrupts the thing running it.
- Trusting the worker's "done" instead of a mechanical diff — shipping empty or hallucinated changes.
- Deploying from a cache the build step never invalidated, so the gate blessed different bytes than ship.
- Leaning on the green gate alone for trust-boundary changes it structurally cannot see.
- A generation worker that can merge its own proposal, or that runs with live privilege instead of in a sandbox.

## Enforcement

All of it is enforcement, by design. The fresh-clone assertion (the workspace must not pre-exist), success decided by a mechanical read of version-control status rather than the worker's report, tested==shipped bound by a digest comparison at the deploy edge, and a landing credential that structurally cannot merge — branch protection with a human on the button. Each is a pipeline step with an exit code; none consults the worker's opinion of its own work.

## Related

- [grounded-verifiable-gates](../grounded-verifiable-gates/SKILL.md)
- [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md)
- [structural-security-boundary](../structural-security-boundary/SKILL.md)
- [reversible-by-default-confirm-consequential](../reversible-by-default-confirm-consequential/SKILL.md)
- [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md)
