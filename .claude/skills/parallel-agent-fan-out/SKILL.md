---
name: parallel-agent-fan-out
description: Use when fanning out many write-capable sub-agents across one build — pre-wire the shared seams, own files disjointly, namespace shared state, and re-run every agent's gate yourself.
---

# Fan Out on Independence, Re-Run Every Gate Yourself

When a large build decomposes into many genuinely independent units, one write-capable sub-agent per unit lands them in parallel wall-clock time. The throughput is real — and so is the new failure surface: agents collide on shared files, clobber each other's state on a shared backend, and report "done" over work that was never proven. The coordinator's job is to design the independence in up front and to trust none of the reports at the end.

## When to use

Reach for this when you are the coordinator about to spawn more than a couple of write-capable agents against one repository or one shared live system — implementing N modules of a large surface, migrating N call-sites, covering N endpoints, porting N files — and the units are independent enough to build in parallel.

Red-flag thoughts — if you catch yourself thinking any of these, STOP and apply this skill:

- "I'll let each agent wire itself into the registry / index / router."
- "They're all hitting the same dev database, it'll be fine."
- "The agent said its tests pass, so that unit is done."
- "I'll split this into ten 'independent' units" — but two of them edit the same file.
- "The live tests are each agent's job; I'll just merge what they hand back."
- "Every unit's review came back clean, so the merged whole is clean."

## The rule

1. **Pre-wire the shared seams before you fan out.** Create every integration point the units plug into — the registry or index that lists them, the stub each will replace, the shared test fixtures and config — yourself, first, in one place. Then each agent fills a leaf and never touches a shared file. Fanning out before the seams exist guarantees N agents editing the same registration file and N conflicts.
2. **Give each agent a disjoint ownership manifest.** Name the exact files it may create or modify, and forbid everything else — the shared seams, another unit's files, global config. Ownership is by file and disjoint across agents; a violation is reverted, not merged. This is [surgical-changes-with-checkpoints](../surgical-changes-with-checkpoints/SKILL.md) enforced at fan-out scale.
3. **Namespace every resource on shared live substrate, and touch only what you created.** When agents exercise one shared stateful backend in parallel — a dev database, a live server, a cloud project — prefix every resource each agent creates (`<unit>-…`) and forbid it from mutating or deleting any resource it did not create; clean up in a finalizer that runs even on failure. Parallel agents share one reality; without namespacing they overwrite each other's fixtures and delete each other's state. This is [secrets-and-teardown-discipline](../secrets-and-teardown-discipline/SKILL.md)'s "own only your scope" made a hard rule.
4. **Isolate the shared execution environment, or the units aren't independent.** Files and backend state are only two of the three collision surfaces; the third is the runtime the agents share — one working tree, one dependency set. Give each agent its own working tree, virtualenv, or container so an install, a global-config change, or an in-flight edit in one cannot break another mid-run. When agents must share one tree and interpreter, forbid environment-mutating operations — package installs and uninstalls, global config edits — anywhere but the coordinator, and treat any file another unit imports as a shared seam even when it sits inside your ownership directory: cut ownership along the import graph, not just the directory tree.
5. **Treat each agent's "done" as a claim, and re-run its gate yourself.** A sub-agent's final report is model output, not a result. The coordinator re-runs the unit's own gate — its tests, its type-check, its lint, its live-integration run — against the merged tree and believes the exit code, not the prose. A unit is not done on a green report over mocks; it is done when *you* watched its gate pass. This is the mechanical check of [autonomous-self-improvement-loop-safety](../autonomous-self-improvement-loop-safety/SKILL.md) and the verdict-over-output rule of [grounded-verifiable-gates](../grounded-verifiable-gates/SKILL.md), applied to delegated development.
6. **Serialize the join.** Agents return content for the shared seams; the coordinator integrates it and runs the whole suite once at the point of integration. A merge conflict on a shared file is a process failure to prevent, not a thing to resolve after the fact.
7. **Cut along real independence, not ambition.** Split where the units genuinely don't touch — one module, one endpoint, one migration target each. If two "units" must edit the same file or coordinate mid-flight, they are one unit; forcing them apart manufactures exactly the cross-unit corruption namespacing was meant to prevent. When in doubt, fewer, larger, truly-disjoint units beat more that secretly overlap.
8. **End with one whole-scope adversarial review of the merged tree.** Per-unit gates are structurally blind to cross-unit residue: unit A deletes a file, unit B's docs still reference it, and both units' own gates pass. After the join, run a single review whose scope is the entire merged change, hunting specifically for what no unit owned — dangling references to artifacts another unit removed, seams two units touched, claims one unit made that another invalidated.

## Why

Fan-out multiplies throughput and multiplies the ways work can silently conflict or silently lie. Two agents mutate the same shared record and each passes its own test while corrupting the other's. One agent uninstalls a dependency another is mid-test on, or edits a module a third imports. An agent edits the file everyone registers into and the merge is a pile of conflicts. An agent reports "all green" over mocks that never touched the real system. None of these is caught by trusting the agents; every one is caught by designing the units to be independent (pre-wire, disjoint ownership, namespaced state, isolated runtimes) and then re-running each unit's gate against the merged whole. The coordinator's leverage is entirely front-loaded and back-loaded: make the middle boring by making the units actually independent, and make the end trustworthy by verifying mechanically instead of reading reports. Skip either half and the speed-up is paid back with interest in a corruption you find late and can't localize.

## In practice

A second build the pack draws on — a REST API client library extended to cover an external system's entire API, roughly 340 endpoints across 15 namespaces, verified against one containerized live server — was built exactly this way. The coordinator first pre-wired the client registry and a stub module for every namespace, then handed each of 15 implementer agents a manifest of exactly its files (sync and async client modules, two unit-test files, one live-integration test, an example, and a docs page) plus a live-server brief, and forbade touching the registry or any other namespace's files. Every resource an agent created on the shared server was prefixed `<tool>-<namespace>-` and torn down in a finalizer, with a standing rule never to touch a resource it hadn't created — which is what kept the agents from clobbering each other's fixtures on the shared backend. The two real cross-agent incidents that happened anyway were not on the data backend at all but on the shared execution environment: one agent transiently uninstalled a shared package another was mid-test on, and another hit a transient import break from a third agent's in-flight edit to a module it imported. Neither was prevented by file ownership or resource namespacing; both were caught only because the coordinator re-ran every namespace's unit and live-integration suite itself instead of trusting the agents' "all green" reports. All 15 units merged with zero failures after that independent re-verification. The portable shape holds on any stack: pre-wire the seams, cut along real independence, namespace on shared substrate, isolate the runtime, serialize the join, and re-run every unit's gate yourself before you believe it.

## Anti-patterns

- Launching the agents before the registry or stubs they plug into exist, so N of them edit the same wiring file and conflict at the join.
- Accepting a sub-agent's "tests pass" as done without re-running that gate against the merged tree yourself.
- Letting parallel agents create un-prefixed resources on one shared backend, so they overwrite and delete each other's fixtures.
- Sharing one working tree and dependency set across all agents, so one agent's install or in-flight edit to an imported module breaks another's run.
- Splitting work into "independent" units that in fact must edit the same file or coordinate mid-run.
- Blessing a unit on green mocks because clearing the live gate was "the agent's job."
- Calling the build done when every per-unit review passed, with no whole-scope pass for the defects that live between units.

---

Related skills:

- [../autonomous-self-improvement-loop-safety/SKILL.md](../autonomous-self-improvement-loop-safety/SKILL.md)
- [../grounded-verifiable-gates/SKILL.md](../grounded-verifiable-gates/SKILL.md)
- [../surgical-changes-with-checkpoints/SKILL.md](../surgical-changes-with-checkpoints/SKILL.md)
- [../battle-testing-on-real-infra/SKILL.md](../battle-testing-on-real-infra/SKILL.md)
- [../secrets-and-teardown-discipline/SKILL.md](../secrets-and-teardown-discipline/SKILL.md)
- [../spec-driven-development/SKILL.md](../spec-driven-development/SKILL.md)
