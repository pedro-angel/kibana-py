---
name: hexagonal-with-enforced-contracts
description: Use when building an app that touches external systems (LLMs, DBs, cloud SDKs, HTTP APIs) — isolate a framework-free core behind ports a linter enforces.
---

# Hexagonal Boundaries Enforced by a Linter

Put your business logic in a core that imports no framework or SDK, reach every external system through a Protocol/interface port, and let an automated import-checker — not reviewer discipline — fail the build when anything inner imports anything outer.

## When to use

Reach for this whenever an app integrates volatile externals — LLM providers, databases, cloud SDKs, message queues, third-party HTTP APIs — and you want those choices to stay swappable and testable.

Red-flag thoughts that mean STOP and apply this skill:

- "I'll just import the SDK here in the logic, it's only one call."
- "We'll all remember to keep the cloud client out of the core."
- "I'll inject it as a generic/`Any`/`object` for now and type it later."
- "Let me build the real cloud adapter first; the local stub can wait."
- "The config/logging module can import from the adapter — it's just a helper."

## The rule

1. **Name the layers and order them.** Driving (entrypoints: CLI, HTTP, jobs) → adapters (concrete integrations) → application (use cases, orchestration) → domain (pure logic + models). Dependencies point only inward. The domain imports nothing but itself and the standard library.
2. **Make every external collaborator a port.** Define an interface/Protocol/abstract type for each seam (storage, LLM, retrieval, clock, mailer). The application depends on the port's signature, never on a concrete class.
3. **Treat an untyped seam as a defect.** If a collaborator is injected as `Any`/`object`/`interface{}`/dynamic, the layer secretly depends on the implementation. Give it a real port type, and pin each adapter to its port with a conformance test (instantiate the adapter, assert it satisfies the port).
4. **Encode the boundary as machine-checked contracts.** Configure an import-boundary checker (Python: import-linter; Java: ArchUnit; TS/JS: dependency-cruiser or eslint-plugin-boundaries; Go: go-arch-lint; or your stack's equivalent) with: (a) a *layers* contract declaring the order above, and (b) a *forbidden-imports* contract banning every external SDK from the domain by name (the graph/agent lib, the HTTP client, the validation lib, the serializer...).
5. **Add fine-grained edge contracts for cross-cutting modules.** Config and telemetry/logging are imported everywhere, so they're easy to let leak upward. Forbid them from importing the outer layers (driving, adapters, application) so they can never reach back up.
6. **Wire the check into the standard developer gate.** Put the contract check beside lint and tests in the one command everyone runs and CI runs (`make check`, `npm run verify`, a pre-merge job — whatever your gate is). A boundary violation must fail the build exactly like a failing test.
7. **Develop against a cheap twin behind the production port.** Stand up a free or local implementation (local model server, in-memory store, fake API) behind the *same* port the production adapter will later occupy. Select between them with an environment-driven factory, so going to production is a config change, not a code rewrite.

## Why

Architecture maintained by vigilance decays: every PR is a fresh chance for an SDK import to slip into the core, and reviewers miss it. A linter contract converts "we agreed not to do that" into "the build is red." Once the boundary is mechanical, the payoffs compound — you can swap providers by config, unit-test the core with no network or cloud credentials, and onboard people without explaining unwritten rules. The cost of skipping it is silent coupling: the day you need to change the database or LLM vendor, you discover the "isolated" core imports it in fourteen places, and there is no test to tell you when you've finished untangling it.

## In practice

On the project this was distilled from — a human-in-the-loop AI agent validated live on a cloud platform then reclaimed via Terraform — the boundary lived in a single import-linter config (`.importlinter`). One *layers* contract declared `driving > adapters > application > domain`; one *forbidden* contract listed the SDKs banned from the domain (an agent framework, `httpx`, `pydantic`, `yaml`); and a third forbade `config` and `telemetry` from importing any outer layer. The check ran inside the project's `make check: lint lint-imports test`, so a stray import failed CI like a broken test.

Every external collaborator was a Protocol. When a semantic retriever was added later, it shipped as a `RetrieverPort` Protocol (`search(terms, top_k) -> list[PageRef]`) — "kept a Protocol like every other collaborator so the application layer depends on a signature, never on the concrete adapter." And because the LLM sat behind a port, development ran against a free local model and later moved to the cloud provider as "a one-line configuration change via the `LLM_PROVIDER` factory — no application- or domain-layer code touched." Replace the specific library names with your own stack and the structure transfers unchanged.

**The contract need not be code imports.** The same move applies to a docs or spec artifact: its contract is a *schema + structural-integrity* rule — every file carries the required frontmatter, an index lists exactly the files that exist on disk, every cross-link resolves — enforced by a commit hook so a broken invariant fails like a red build rather than slipping past a tired reviewer. This pack ships that as a reference implementation: `templates/git-controls/` holds a `.pre-commit-config.yaml` plus zero-dependency POSIX-sh validators that assert its own frontmatter shape, index-vs-directory parity, and link resolution on every commit — the identical "let a machine fail the build, not a human notice" pattern, applied to prose.

## Anti-patterns

- Relying on code-review vigilance — not an automated contract — to keep SDKs out of the core.
- Injecting a concrete adapter as `Any`/untyped so the application secretly depends on the implementation, with no conformance test to catch it.
- Building the expensive cloud adapter first instead of a cheap local twin behind the identical port.
- Letting config or telemetry modules import upward into adapters/driving, quietly inverting the dependency arrow.

## Enforcement

What a machine can check: everything that matters. An import-linter / ArchUnit / dependency-cruiser contract that fails the build the moment domain code imports an adapter or a vendor SDK — running in CI, fail-closed: a missing, empty, or skipped contract is a FAIL, not a pass. The boundary either has a machine on it or it does not exist; a reviewer's eye is defense-in-depth, never the seam.

---

Related skills:

- [../configuration-single-source-of-truth/SKILL.md](../configuration-single-source-of-truth/SKILL.md)
- [../grounded-verifiable-gates/SKILL.md](../grounded-verifiable-gates/SKILL.md)
- [../additive-default-off-feature-flags/SKILL.md](../additive-default-off-feature-flags/SKILL.md)
- [../battle-testing-on-real-infra/SKILL.md](../battle-testing-on-real-infra/SKILL.md)
- [../structural-security-boundary/SKILL.md](../structural-security-boundary/SKILL.md)
