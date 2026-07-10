---
name: environment-research
description: Use when a spec or plan is about to depend on a dependency, library, API, CLI, or platform whose real behavior you have not personally observed — run a small real experiment before trusting docs or memory, and let the observed result outrank documentation when they disagree.
---

# Probe the Dependency Before You Design On It

Documentation describes what a dependency is *supposed* to do; its source describes what it was *written* to do. Neither tells you what it *actually* does under your input, at its edges, or when it fails — you don't know until you run it. Before a spec or plan leans on a claim about a dependency's behavior, spend the ten minutes to turn that claim into an observation.

## When to use

- Before a spec, plan, or design decision depends on a library, API, CLI, model, or platform whose real behavior you have not personally observed.
- The docs are thin, ambiguous, contradictory, or you suspect they're stale.
- A boundary, error, or concurrency behavior will drive a design decision — a retry policy, a schema, a timeout, an auth flow.

Skip it for dependencies you've already empirically characterized, or questions with no design consequence.

Red-flag thoughts that mean STOP and apply this skill:

- "The docs say it returns X, that's good enough."
- "I read the source, so I know what it does."
- "It probably behaves like every other API in this family."
- "I'll find out when it breaks in prod."
- "The changelog says this was fixed in the version we're pinned to." (Did you check the pinned version, or the latest?)

## The rule

1. **State your hypothesis precisely**, in terms of the dependency's execution (what happens on the happy path), outcome (the shape/type of what's returned), error (how it fails — exception, null, partial write, silent), and boundary (empty input, huge input, concurrent callers, timeouts, rate limits).
2. **Write the smallest experiment that could falsify the hypothesis** — install the package, hit the real endpoint, call the real CLI, one call at a time. Smallest code that produces one observation.
3. **Run it against the real thing** — the actual installed version, the actual live endpoint — never a doc example, a cached response, or a colleague's recollection.
4. **Record what you saw, not what you expected**: the exact version, the date, the input, the observed output or error. This record is the artifact a reviewer or a future session checks instead of rerunning the probe.
5. **Provoke the failure modes on purpose** — empty input, an oversized payload, a second concurrent caller, an expired token. A mode you never triggered is a mode you didn't characterize, and it's usually the one that breaks the guarantee your design depends on.
6. **When the observation contradicts the documentation, the observation wins.** Design against what you saw, and write the divergence into the spec or the code the next reader hits — not into a chat transcript that evaporates.
7. **Keep the experiment disposable; harvest only the finding.** A line in the spec's research section, a dated note in project memory — the probe script itself doesn't need to survive the session that wrote it.

## Why

A fluent, plausible-sounding claim about a dependency is exactly as dangerous whether it comes from a model, a stale doc, or your own memory of a similar tool — it's uncorrelated with whether it's true. Reading the source tells you intent, not behavior: a library can be written to validate input and still ship a code path where it doesn't. Only running the real thing, at its real version, against a real input, produces a fact instead of an inference. And the failure this catches is expensive precisely because it's silent until the design built on it hits the boundary in question — often in production, from a user, long after the "probably fine" assumption stopped being cheap to unwind.

## In practice

Adapted from cmanaha/extended-superpowers (MIT), rewritten here as a general research discipline with no tie to any specific tool, hook, or bundled agent — any environment capable of running the real dependency and recording the result can fill this role. Two recurring shapes of the failure motivate it, genericized from real incidents: a published OpenAPI document typed a field as writable, but the live server silently rejected any write to it — the only way to know was one real `PATCH` call, not a closer read of the spec. Separately, an HTTP client framework silently stripped the `Authorization` header on redirect unless a specific flag was set — a behavior no amount of reading the framework's front-page docs surfaces, because it's disclosed three issues deep in an unrelated thread. Both would have shipped a wrong assumption into a design had the real call not been made first; in both cases, the fix was one line, but finding it required treating the documentation as a hypothesis rather than a fact.

## Anti-patterns

- Designing a schema, retry policy, or auth flow off documentation you never tested against the running dependency.
- Reading a dependency's source and treating "what it was written to do" as "what it does."
- Running only the happy path and declaring the dependency understood.
- Discovering a divergence between docs and reality and letting it live only in chat history instead of the spec or the code.
- Treating "I'll find out in QA" as a substitute for a five-minute probe now.

## Enforcement

What a machine can check: the residue, not the curiosity. A recorded observation everywhere a design claim leans on a dependency — a dated research entry in the spec (structure lint), the divergence written into the code the next caller reads, a decision-memory note pinning the exact version probed. The probe script is disposable by rule 7; what fails closed is a spec claiming dependency behavior with no observation behind it — the factual-grounding lens of [adversarial-lens-review](../adversarial-lens-review/SKILL.md) reviews exactly that.

## Related skills

- [spec-driven-development](../spec-driven-development/SKILL.md)
- [battle-testing-on-real-infra](../battle-testing-on-real-infra/SKILL.md)
- [decision-memory](../decision-memory/SKILL.md)
- [adversarial-lens-review](../adversarial-lens-review/SKILL.md)
