---
name: structural-security-boundary
description: Use when containing untrusted or agent-generated execution, sandboxing a worker with write/exec tools, or judging whether a guard is actually a security boundary.
---

# The Real Boundary Is Structural; String Guards Are Labelled Defense-in-Depth

A guard that lives in the same trust domain as the actor it constrains is not a boundary — it is a speed bump the actor owns. Put the real boundary in a layer the actor cannot reach (a separate identity, a read-only mount, dropped capabilities, a VM), keep pattern/command guards as honest secondary friction that fails toward asking, and when you cannot yet reach the structural bar, label the residual and pin it as a test rather than letting a cooperative check masquerade as containment.

## When to use

Reach for this whenever code you do not fully trust will execute: sandboxing an agent worker that holds write or shell tools, containing generated or third-party code, hardening a privileged registry or credential store, or answering "is this actually safe?" in a review.

Red-flag thoughts — if you catch yourself thinking any of these, STOP and apply this skill:

- "The regex blocks the dangerous command." (an alias, an obfuscation, or a subprocess slips it)
- "The prompt tells the worker not to touch that file." (a prompt is not a boundary)
- "It runs as the same user, but we check the path first." (same-privilege code can rewrite the check)
- "We'll add a deny-list." (deny-lists enumerate the bypasses you thought of; the attacker finds the others)
- "The isolation is structural." (is the separate UID / mount / namespace actually provisioned, or just planned?)

## The rule

1. **Make the boundary structural.** What actually stops a hostile or confused actor is an OS-level mechanism it cannot reach from inside its own trust domain — a separate UID that gets `EACCES` on what it must not touch, a read-only mount, dropped capabilities plus seccomp, or a VM. A shared-kernel namespace or container *reduces* blast radius but does not fully contain a determined attacker (escapes are routine); treat it as a weaker tier than a separate UID + caps or a VM, not as "the boundary."
2. **Treat pattern/command guards as labelled defense-in-depth that fails toward asking.** They add friction and catch honest mistakes, but they are bypassable by obfuscation, aliasing, or laundering through a subprocess; never present one as the boundary. Prefer an allow-list fast-path over a deny-list.
3. **Fail closed and deny by default.** Absent, empty, malformed, or ambiguous input denies. A missing field is not a pass, and an unrecognized alias is not permission.
4. **Grant least privilege.** The narrowest identity, scope, and capability set that works, so a compromise's blast radius is small. (→ [secrets-and-teardown-discipline](../secrets-and-teardown-discipline/SKILL.md))
5. **When you cannot make it structural yet, say so — and pin it.** Name the residual exactly (what this does NOT contain, and the precise bypass), and encode it as a passing-by-design test so a future change cannot silently erode it. Structure is not resistance until proven. (→ [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md))
6. **Let a machine enforce the seam, not reviewer vigilance.** Encode the boundary where the build or the platform applies it automatically — an import contract the build fails on, a policy the orchestrator applies at spawn, an init system that mounts it read-only — so the isolation survives the next contributor who never read this. This is the build-time/architecture seam that keeps rule 1's runtime boundary in place. (→ [hexagonal-with-enforced-contracts](../hexagonal-with-enforced-contracts/SKILL.md))
7. **Never self-certify a security change.** A trust-boundary change is reviewed by someone who did not write it; the gate flags it for that owner review rather than blessing it automatically. (→ [reversible-by-default-confirm-consequential](../reversible-by-default-confirm-consequential/SKILL.md))

## Why

A guard in the same trust domain as the attacker can be defeated by the attacker: string matching loses to obfuscation and laundering, and a same-privilege check can be overwritten by the very code it was meant to constrain. Only a mechanism enforced by a lower layer — the kernel, the filesystem, the build — holds when the actor is hostile rather than merely clumsy. That is why "we check the command" and "we told it not to" are speed bumps, not walls. And when you genuinely cannot reach the structural bar yet, an honestly labelled and test-pinned residual is worth more than a comfortable illusion: it tells the next reader exactly where the real edge is, instead of letting a cooperative guard be mistaken for containment until the day someone tests it.

## In practice

Consider an agent platform that runs a write-capable worker. A command-pattern guard that denies dangerous actions is launderable — an attacker aliases the command or runs it through a subprocess and the pattern never matches — so that guard belongs as defense-in-depth that fails toward asking, not as the boundary. The boundary belongs in structure: run the worker under a separate identity, and own the privileged control state with an identity the worker cannot write, so even a fully subverted worker gets a permission error instead of forging authority. If that separate-identity isolation is not yet provisioned, the honest move is to name the gap as an explicit residual and pin it as a passing-by-design test, so "this is cooperative, not structural, until the identity split lands" cannot quietly harden into an unearned "secure." The shape generalizes to any stack: put the boundary in a layer the actor cannot reach, keep string guards as honest secondary friction, deny by default, and pin what you cannot yet enforce.

## Anti-patterns

- Selling a regex or command deny-list as the security boundary.
- A prompt instruction ("don't edit X") standing in for a mechanism.
- A same-privilege check guarding state the guarded process can itself overwrite.
- Claiming "structural isolation" while the isolating mechanism is only planned, with no labelled residual.
- Self-certifying a trust-boundary change instead of routing it to an independent owner review.

## Enforcement

What a machine can check: the boundary, by failing through it. Tests where the sandboxed identity attempts the forbidden write or exec and pass only on the permission error; named residuals pinned as passing-by-design tests so a cooperative check can never masquerade as containment; CI running the worker under the restricted identity, not root. A guard you cannot write a failing test against is not a boundary — it's a hope with a comment.

## Related

- [reversible-by-default-confirm-consequential](../reversible-by-default-confirm-consequential/SKILL.md)
- [secrets-and-teardown-discipline](../secrets-and-teardown-discipline/SKILL.md)
- [hexagonal-with-enforced-contracts](../hexagonal-with-enforced-contracts/SKILL.md)
- [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md)
- [autonomous-self-improvement-loop-safety](../autonomous-self-improvement-loop-safety/SKILL.md)
