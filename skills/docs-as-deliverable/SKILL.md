---
name: docs-as-deliverable
description: Use when shipping or handing off code — treat docs as a first-class deliverable: present-tense, diagrammed-as-code, verified against reality, reader-tested.
---

# Docs as a First-Class, Diagrammed, Tested Deliverable

Documentation is a deliverable, not exhaust. Hold it to the same bar as the code: tight present-tense prose, diagrams expressed as code, every signature and flag verified against the implementation, and comprehension proven by readers — not assumed.

## When to use

Apply whenever you ship code, hand a project to another team, write or revise a README/ARCHITECTURE/runbook, or change behavior that an existing doc describes. Documentation work belongs in the same change as the code it documents — not a follow-up "docs pass" that never comes.

Red-flag thoughts that mean STOP and apply this skill:

- "I'll update the docs later / in a separate PR."
- "The diagram is close enough — the code only moved a little."
- "This describes how it *should* work" (instead of how it does).
- "Everyone on the team already knows this, so I don't need to spell it out."
- "I'll keep the old design doc around as-is; people will figure out it's outdated."
- "I'll hand-type the config table into the docs so it reads nicely."

## The rule

1. **Write to a reader, in present tense, about what is.** Describe the system as it actually behaves now. Cross-link instead of repeating; one authoritative statement per fact. Cut hedging and filler.
2. **Verify every concrete claim against the source.** Open the code/config and confirm each function signature, CLI flag, endpoint path, env var, and default. If you cannot verify it, either verify it or do not claim it.
3. **Express architecture and flows as diagrams-as-code.** Embed parseable diagrams (e.g. Mermaid) directly in the markdown: a context/container view of the system, a sequence diagram for any multi-step or pause/resume flow, a state machine for lifecycle, and a swap map showing which interfaces have which interchangeable implementations. For graph-shaped diagrams, put a small node/edge table beside the diagram so prose, picture, and code can be checked against each other.
4. **Change the diagram in the same commit as the code.** When you alter a flow, a boundary, or a state, update its diagram in that same change so it tracks implemented reality and never silently drifts.
5. **Generate authoritative tables; don't hand-copy them.** Tables of flags, routes, config keys, or metrics should be produced from the code/config (a script, a `--help` dump, a schema export) rather than maintained as a parallel hand-edited copy that rots.
6. **Fence off superseded docs; never silently delete or silently keep them.** Preserve historical/design artifacts for provenance, but put a one-line banner at the top pointing to the current authoritative doc, so no reader mistakes a stale snapshot for truth.
7. **Test the docs with context-free readers.** Have several reader agents or people, each holding only the documentation (no codebase, no tribal knowledge), try to act on it from a distinct persona — new developer, on-call/SRE, end user, skeptic. Log every point where they get stuck, guess, or are misled as a documentation defect, and fix it like a bug.

## Why

Docs are the interface a stranger meets before the code. If they are aspirational, unverified, or drifted, the cost is paid later and larger: a new hire burns a day on a flag that was renamed, an on-call engineer follows a runbook into an outage, a client integrates against an endpoint that no longer exists, a reviewer trusts a diagram that lies about the data flow. Verifying against source, generating tables, and binding diagram changes to code changes remove whole classes of drift at the source. Reader-testing converts "I think this is clear" into evidence that someone with no prior context can actually act — which is the only definition of clear that matters.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent deployed to a cloud runtime — the docs were rewritten as a coherent client-facing deliverable in one focused pass: present-tense, with every function signature, CLI flag, and endpoint re-checked against the live code before being written down. That same pass also *deleted* the development-history docs (BRIEF, DESIGN, SPECS, PAPER, ...) — the very anti-pattern this skill warns against — and the correction was a delete→restore→banner arc: the artifacts were restored, then marked as historical with a dated one-line banner pointing at the current authoritative doc, so provenance survived without anyone mistaking a stale snapshot for truth. The architecture doc gained four embedded diagrams in a single change: a context view of the whole system, a sequence diagram of the pause/resume handoff to a human, a map of which ports were backed by which adapters, and a container view; the agent-framework view additionally carried a node/edge table beside it so prose, picture, and code stayed mutually checkable. The operations runbook generated its table straight from config rather than hand-copying it — "the table below is generated from it" (`docs/OPERATIONS.md`). Finally, the docs were graded by context-free reader agents given *only* the documentation, each reading as a new developer, an SRE, an end user, and a skeptic; their comprehension failures were filed and fixed as documentation defects (recorded in the evaluation write-up). You can apply all of this without knowing that project: write present-tense and verified, embed your diagrams as code and update them with the code, generate your tables, restore-and-banner old docs rather than deleting them, and let fresh readers prove the result.

## Anti-patterns

- **Aspirational docs:** describing intended or hoped-for behavior instead of what the code actually does today.
- **Drifting diagrams:** ASCII art or external diagram files (or screenshots) that no longer match the implemented graph because nothing forces them to move with the code.
- **Unmarked or deleted history:** erasing development/design docs (losing provenance) — or leaving them unbannered so they get mistaken for current truth.
- **Untested docs:** treating documentation as an afterthought that is never checked against whether a newcomer with no context can act on it.

---

Related skills:

- [spec-driven-development](../spec-driven-development/SKILL.md)
- [configuration-single-source-of-truth](../configuration-single-source-of-truth/SKILL.md)
- [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md)
- [decision-memory](../decision-memory/SKILL.md)
