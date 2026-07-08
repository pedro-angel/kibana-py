---
name: surgical-changes-with-checkpoints
description: Use when editing code, configs, or docs — make the smallest correct diff, checkpoint before risky work, and write commits that justify themselves.
---

# Surgical Diffs, Reviewable Checkpoints, Evidence-Citing Commits

Change exactly what the task requires and nothing more. Save a known-good version before you risk breaking things, and write each commit so a stranger can see what changed, why, and what proved it correct.

## When to use

Every time you edit a file, stage a change, or write a commit message. Especially before edits that could break a working state: migrations, dependency bumps, refactors, infra changes, anything touching code you don't fully understand yet.

Red-flag thoughts that mean STOP and apply this skill:

- "While I'm in here, I'll also clean up / rename / reformat this."
- "I'll just commit everything together, it's all related."
- "I don't need a checkpoint, this change is small."
- "The commit message is obvious from the diff."
- "I'll tidy the surrounding code so it's consistent."

## The rule

1. **Bound the change to the stated intent.** Restate the goal in one sentence. Touch only what that sentence requires. If you find unrelated improvements, note them separately — do not fold them in. A diff that says "no content edits; no code touched" is a feature, not a limitation.
2. **Match existing conventions.** Mirror the surrounding code's style, naming, error handling, and file layout. The smallest correct diff is the one a reviewer barely notices.
3. **Checkpoint before risky work.** Commit the current working state first ("checkpoint: working X before Y") so there is always a version to fall back to. Equivalents: a checkpoint commit, a stash, a throwaway branch, a tagged snapshot. Pick whichever your environment supports — but make the fallback exist before you start.
4. **Split by reason, one reason per commit.** If a change has several motivations, make several commits, each with a single-purpose, conventionally-typed prefix (`fix:`, `feat:`, `refactor:`, `docs:`, `test:`, `chore:` in the Conventional Commits scheme — map these to your project's commit convention if it differs). Never blend a bugfix, a refactor, and a doc tweak into one blob.
5. **Write commits as decision records.** State *what* changed and *why*. Group the body by dimension when it spans concerns — Code / Tests / Docs / Fixtures / Infra. Cite the evidence artifact that validates the claim (test output, a results file, a reproduced bug, a real-infra run), and list bugs found-and-fixed along the way.
6. **Restore and copy verbatim, and say so.** When you bring back or duplicate prior content, take it from a named prior version and state the source explicitly ("restored verbatim from <SHA>^"). Do not paraphrase from memory.
7. **Carry provenance.** Keep auditable trailers — co-author lines, a session or ticket link, the reviewer — so the history traces back to who and what produced it.
8. **Pause on request.** If the human wants to inspect the diff first, leave the fix set uncommitted and hand them the change to review. Do not commit ahead of their review.

## Why

Small, single-purpose diffs are reviewable, revertable, and easy to binary-search through; a mixed blob is none of these — when it breaks something, you cannot revert one concern without losing the others, and binary-searching history to find the breaking change (git bisect) lands on a commit that did four things. A checkpoint is the difference between "undo the last commit" and "reconstruct what I had an hour ago." And a commit message that records *why* plus *what proved it* turns your history into the project's memory: months later it answers "why is this like this?" without an archaeology dig, and it lets a reviewer trust the change without re-deriving it. The cost of skipping this is paid later, by someone with less context than you have right now.

## In practice

On the project this was distilled from — a hexagonal, human-in-the-loop AI agent shipped to a cloud runtime — two patterns recur. A restoration commit reads: *"Restored verbatim from the pre-change commit ... No content edits; no code touched"* — the scope is stated so a reviewer needs zero diff-reading to trust it. A risky-change commit reads: *"Validated on a fresh throwaway cloud project ... Evidence: docs/evidence/deep-review-e2e.json"* — the claim "this works" is backed by a named artifact anyone can open (your runtime need not be any particular cloud; the transferable move is cite-the-evidence-artifact). And when the human said *"Surgical changes, please ... commit before so we have at least this version"* and later *"Do not commit, so I can see any correction you make,"* the agent checkpointed first, then held the fix set uncommitted for review. You can apply all three without knowing anything about that project: bound the scope and say so, cite your evidence, checkpoint before risk, and stop when asked.

**Machine-check the discipline you can.** Rules 4 and 7 — the conventional type prefix and the provenance trailer — are exactly the habits that decay under deadline pressure, so enforce them with a `commit-msg` hook rather than relying on memory. This pack does: `templates/git-controls/` pairs the off-the-shelf `conventional-pre-commit` (which checks the header type) with a tiny POSIX-sh hook that rejects any commit body lacking a `Co-Authored-By:` / `Evidence:` / `Refs:` trailer — so a commit that forgets its evidence fails at write time, the same way a boundary linter fails a bad import.

## Anti-patterns

- One opaque commit mixing unrelated concerns (bugfix + refactor + reformat) so nothing can be reverted or understood in isolation.
- A one-line message stating *what* changed but not *why* or *what proved it*.
- Opportunistic refactoring during a bugfix, widening the diff past the intent and burying the actual fix.
- Making risky edits with no prior checkpoint, leaving no working version to fall back to.

---

Related skills:

- [spec-driven-development](../spec-driven-development/SKILL.md) — agree on the intent before you bound the diff to it.
- [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md) — produces the evidence artifact your commit cites.
- [additive-default-off-feature-flags](../additive-default-off-feature-flags/SKILL.md) — keep risky changes inert until proven, an additive sibling to the surgical diff.
- [decision-memory](../decision-memory/SKILL.md) — commits-as-decision-records feed the project's durable memory.
