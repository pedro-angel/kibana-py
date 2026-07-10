---
name: decision-memory
description: Use when a decision, gotcha, or preference would otherwise be re-derived next session — capture it as an indexed note, then verify before trusting stale ones.
---

# Persist Non-Obvious Decisions Across Sessions

When you discover *why* something must be done a certain way — a decision, a trap, a preference — write it down at that moment as a small, dated, cross-linked note. A rationale that lives only in chat history is lost the instant the session ends, and the next session pays to re-derive it.

## When to use

Reach for this the moment you learn something a future session would otherwise have to rediscover:

- A non-obvious choice with a real reason ("we pinned X because Y breaks Z").
- A gotcha with an exact remediation (a flaky timing window, a silent deprecation warning, a model that loops on a certain prompt).
- A stable user or project preference ("always do A before B").
- You are *resuming* work and can't remember where the last session left off.

Red-flag thoughts — if you catch yourself thinking any of these, STOP and write the note:

- "I'll remember this." (You won't. The session will end.)
- "It's obvious why we did it this way." (It won't be obvious next week, to you or anyone.)
- "I'll document it later when I clean up." (Later never comes; the rationale is freshest now.)
- "The old note says X, so X." (Notes go stale — verify before you trust.)

## The rule

1. **Capture at the moment of discovery.** When the rationale is fresh, write a note stating the decision *and* its exact remediation or workaround. Don't wait for a cleanup pass.
2. **One fact per note.** Each note covers a single concern — so when the verify step (rule 7) finds one fact has gone stale, you edit exactly that note in place without rewriting a wall of unrelated prose around it. A five-findings-in-one note can't be surgically corrected.
3. **Put every note behind one index.** Maintain a single entry-point file that lists and links every note with a one-line summary. The index exists for exactly one job: a cold-start session with no chat history reads it first and learns what it already knows — an un-indexed note is unreachable, so effectively unwritten.
4. **Give each note frontmatter:** a short name, a one-line description, the date, and which session/task produced it. Attribution lets a future reader judge freshness and provenance.
5. **Cross-link into a graph, not a pile.** When two notes relate, link them to each other and to the durable project doc (README, ops runbook, ADR) — so a future session that lands on one note follows the link to the related rationale and the canonical doc instead of re-deriving the connection. Explicit links beat re-explaining the same context inline in each note.
6. **Track completion state in the index.** Mark workstreams as queued / in-progress / done so a resuming session knows what's live without re-reading everything.
7. **Verify stale or surprising claims before acting on them — but only when it matters.** Re-check a note against current reality (run the command, hit the API, read the current config) *before it drives an irreversible or load-bearing action, or when it predates a known change to the system it describes*; a routine read of a fresh note needs no ceremony. If reality changed, update the note *in place* — don't leave a contradicted note standing.

## Why

The expensive part of agent work is not typing code — it's the reasoning that produced a non-obvious choice. That reasoning is path-dependent: it took a failed attempt, a confusing error, or a careful experiment to arrive at. If it evaporates with the chat, the next session repeats the failure, re-reads the same docs, and re-runs the same dead-end experiment. A two-line indexed note converts that one-time cost into a permanent asset. The index and cross-links are what make it *retrievable* — an un-indexed note is nearly as lost as no note. And the verify step is what keeps the memory trustworthy: a stale note that's blindly trusted is worse than no note, because it actively misleads.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent shipped to a cloud runtime — an end-to-end run wrote its results to an evidence JSON file, and one field flagged a serialization library quietly warning that its current message format "will be blocked in a future version." Rather than let that scroll past in the run log, the agent captured it as a *forward-compat note in that evidence JSON*: the symptom, the two remediations (register the domain models with the serializer, *or* keep the library pinned before any major upgrade), and a pointer to the ops-runbook's troubleshooting section. A separate note recorded a live gotcha — the search index *lags* document creation, which matters for test timing but not for real usage — so a future session wouldn't "fix" a non-bug. All notes sat behind a single index file that listed each workstream and its state (one eval task marked done, the next marked next). When a licensing flag later flipped, the relevant note was edited in place rather than left to contradict reality. None of this requires knowing that specific project: the move is *discover → write one small dated note → index it → link it → verify before reuse*, in whatever note store your setup provides (a `memory/` folder, a docs directory, an issue tracker, an ADR log).

## Anti-patterns

- Letting a hard-won rationale live only in the chat that found it — gone at session end.
- Dumping many facts into one sprawling note with no index and no cross-links — unfindable, so effectively unwritten.
- Trusting an old note without re-checking it against current reality — and acting on a claim that has silently gone false.
- Leaving a note that new findings have contradicted unedited — letting the memory rot into a trap for the next reader.

## Enforcement

What a machine can check: that no note can be silently orphaned. An index-completeness check — every note linked from the index, every link resolving (this pack's own check-readme-index and check-crosslinks-resolve are the worked pattern) — and dates on every note so staleness is at least visible. Whether a note still holds is judgment the skill already assigns (verify before trusting); the machine just guarantees you can find what needs verifying.

---

Related skills:

- [spec-driven-development](../spec-driven-development/SKILL.md)
- [surgical-changes-with-checkpoints](../surgical-changes-with-checkpoints/SKILL.md)
- [docs-as-deliverable](../docs-as-deliverable/SKILL.md)
- [honest-reframing-over-overclaiming](../honest-reframing-over-overclaiming/SKILL.md)
