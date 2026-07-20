---
name: currency-and-audit-before-trust
description: Use when making a load-bearing or security-relevant claim, or reusing inherited or unfamiliar code — treat recalled facts and unread code as unverified until re-grounded against the live source, and disposition every dangerous surface rather than eyeballing it.
---

# Recalled Is a Hypothesis; Inherited Is Guilty Until Proven

A fact you did not just observe from the current primary source — your memory, a document, a prior note, a fluent answer, a report from another step — is a hypothesis, not a fact, and may not drive an irreversible, load-bearing, or security action until you re-ground it against the live artifact at its real version. Code you inherited is untrusted until its behaviour is proven by observation, not by reading it. And a dangerous construct found anywhere is guilty until a machine-parseable check proves it inert — you never downgrade it by eye ("probably a comment") or defer the check ("glance later").

## When to use

Reach for this before any assertion or action whose cost of being wrong is real: shipping a load-bearing claim, reusing or modifying inherited/unfamiliar code, or handling a dangerous construct (a privilege-bypass flag, a wildcard grant, an `eval`, unbounded egress). The more irreversible or security-relevant the step, the harder it bites.

Red-flag thoughts — if you catch yourself thinking any of these, STOP and apply this skill:

- "I remember this API/behaviour does X." (you did not just read it at the current version)
- "It's probably a comment / probably dead / probably fine." (probably is not a disposition)
- "I'll verify that later." (a deferred check is an unverified claim shipping now)
- "The suite is green and the code is here, so it's trustworthy." (green + present is not provenance)

## Currency: re-ground before you rely

- **Recalled facts are hypotheses.** Anything not freshly observed from a current primary source is a claim to re-verify, never a basis for action. The more irreversible or security-relevant the action, the harder this bites.
- **Read the actual bytes at use-time.** For any claim about code or config, open the file at the current checkout, quote the exact line, and cite `path:line@commit`. "I saw it earlier", "it's probably X", and "I'll check later" are forbidden as the basis of an assertion.
- **Observation outranks docs and memory.** When behaviour matters, run the smallest real experiment against the real thing at its real version and record what you saw, not what you expected. When observation contradicts a document, the observation wins and the document becomes a defect to fix.
- **Provenance or it didn't happen.** Every load-bearing claim carries where and when it was observed — `path:line@commit`, `endpoint + status + date`, or `command + exit-status`. No attached provenance means unverified, which means it cannot ship.

## Dangerous surfaces: disposition, don't eyeball

- **A dangerous construct is guilty until proven inert** — a privilege-bypass flag, a wildcard grant, an `eval`, an unbounded network egress. Its mere presence is the finding, independent of whether it looks reachable, because one future edit can re-arm a dead one.
- **Parse, don't string-match, for any safety verdict.** Whether a line is a comment, a string, reachable, or actually executed is a parse question. A judgment that pattern-matches is defense-in-depth that must fail toward asking — never the boundary.
- **Stop-and-verify on discovery.** The moment you find a dangerous construct, resolve it before continuing: prove it inert with a machine check, disposition it with a recorded reason, or remove it. Never carry it forward unacknowledged.

## Inherited code: behaviour, not reading, is the proof

- **You cannot recover trust by re-reading.** Source inspection alone cannot establish trust — the classic result is that a compromised tool hides its own trojan from its own source, and verifying the source recurses forever into the tools that built it. Trust is reconstructed from observed behaviour under controlled execution plus provenance, not from reading or recall.
- **Characterize before you change.** Pin the actual current behaviour of inherited code in a test before modifying it — describe what it *does*, not what it *should* do — so a change that alters behaviour fails loudly.
- **Every inherited unit carries provenance.** Where did it come from, when, and what proves it still holds? Orphaned code with no provenance and no behavioural test is untrusted by default; disposition or delete it, never leave it "probably fine".

## Why

The failure this prevents is quiet and recurring: a remembered fact that had gone stale drives an irreversible step; a dangerous flag dismissed as "probably a comment" gets re-armed by the next edit; inherited code trusted because it was present and the suite was green turns out to do something no test pinned. Each is cheap to catch at the moment of use with a re-grounding or a machine check, and expensive after it has shipped a wrong load-bearing claim. Observation-plus-provenance is the only thing that survives contact with a hostile or merely stale reality.

## When you're fooling yourself

- Asserting a remembered API or behaviour without re-reading the live source at its current version.
- "Probably a comment" / "worth a glance later" standing in for the disposition of a dangerous token.
- Trusting inherited code because it is present and the suite is green, with no test that pins its actual behaviour.
- Shipping a load-bearing claim with no `path:line@commit` / `command+exit` provenance attached.

## Enforcement

Documented rules erode under pressure — turn the load-bearing ones into gates that fail closed. What a machine can hold: a check that refuses a change that leaves a dangerous surface without a recorded disposition — its presence is the finding, and an inline recorded reason (an acknowledgement) is the only way past; a provenance field the definition-of-done requires on load-bearing claims; a drift guard that fails when a pinned artifact changes without its record updated in the same change; a characterization test that pins inherited behaviour so a silent change fails loudly. What honestly stays judgment: whether a surface is *genuinely* inert, and whether a disposition's stated reason is sound — which is why the machine check forces an acknowledgement rather than granting trust. A rule a human must remember is a rule that will be forgotten at the worst moment.

## Related

- [grounded-verifiable-gates](../grounded-verifiable-gates/SKILL.md)
- [structural-security-boundary](../structural-security-boundary/SKILL.md)
- [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md)
- [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md)
- [autonomous-self-improvement-loop-safety](../autonomous-self-improvement-loop-safety/SKILL.md)
