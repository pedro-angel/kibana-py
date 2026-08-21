# Multi-Version Kibana Support — Brief

**Date:** 2026-08-21
**Status:** Approved — feeds RESEARCH → SPECS → DESIGN → TASKS → build
**Phase:** 1 of 5 (BRIEF). Consumes: nothing. Feeds:
[`docs/superpowers/notes/2026-08-21-multi-version-support-research.md`](../notes/2026-08-21-multi-version-support-research.md).
**Review:** adversarial self-review, §6. No independent human review — see the honesty note there.

## 1. The problem

`kibana-py` claims to support two Kibana minor lines and supports one.

The claim is in `README.md` "Version support": the two most recent minor lines, at the
latest patch of each. The reality, measured on 2026-08-20 and recorded in
[`docs/evidence/cloud-environment-battle-test.md`](../../evidence/cloud-environment-battle-test.md),
is that nine integration tests pass on 9.4.3 and fail on 9.5.1. The README says so, the
release gate deliberately blocks on 9.4.3 alone, and the 9.5 row reads "In progress".

Two further problems sit underneath that one:

- **The pins are stale.** The repository targets 9.4.3 and 9.5.1. The latest patch of each
  line is 9.4.5 and 9.5.2. A policy phrased "the latest patch of each" that is two patches
  behind is a policy nobody is executing.
- **The supported set is declared in ten places.** `elastic-start-local/.env.example`,
  `.github/workflows/integration-probe.yml`, `.github/workflows/release.yml`,
  `scripts/cloud-setup.sh`, `README.md` (four separate statements),
  `docs/source/development/cloud-environment.md`, `docs/source/quickstart.md` and
  `examples/README.md` each carry a hand-written version string. Moving the supported set
  forward means ten coordinated edits, and nothing fails when one is missed — which is why
  several already disagree.

## 2. The goal

A caller writing against `kibana-py` gets the same client contract on Kibana 9.4.5 and
9.5.2, and the repository can move that supported set forward without a research project
each time.

Concretely:

1. Every integration test that passes on one supported line passes on the other, or the
   difference is a deliberate, documented, version-gated behavior.
2. The supported set is declared **once** and every other mention is checked against it by
   a gate, not by a reviewer's memory.
3. Adding a new Kibana line is a bounded, repeatable procedure, and it forces an explicit
   decision about whether the oldest supported line still earns its place.

## 3. Why now

Kibana ships a minor line roughly every eight weeks. Each one that lands while the client
tracks a single version widens the gap between the README's claim and the code's behavior.
The 9.5 gaps were measured in August and are the second such finding; without a standing
procedure the third will be found the same way — by a caller, in production.

## 4. Scope

**In scope**

- Client behavior on Kibana 9.4.5 and 9.5.2, verified live against both.
- A single source of truth for the supported set, with a gate over every mirror of it.
- A version-support policy including a recurring, recorded decision on dropping the oldest
  line.
- Reconciling README, docs, CI matrix and the release gate onto the above.

**Out of scope**

- Supporting Kibana 9.3 or earlier. The policy is two lines; 9.3 is the third.
- Serverless / Elastic Cloud-hosted Kibana. Neither is provisioned for this repository's
  tests, and claiming support for an untested target is the failure this brief exists to
  correct.
- Re-implementing the internal `/internal/significant_events/*` surface that 9.5 introduced.
  It is internal, unversioned, and outside the client's stated public-API remit.

## 5. Definition of done

- `make dod` reports GO.
- The integration suite runs on live 9.4.5 **and** live 9.5.2 with no failure attributable
  to a version difference the client could have absorbed.
- A committed evidence artifact pins both runs: commands, versions, commit, per-suite result.
- The release gate blocks on both lines, not one.
- Deleting a version string from any mirrored location fails a gate.

## 6. Adversarial self-review

Recorded because the methodology requires a review verdict in the doc, and honesty requires
saying which kind it was. **This is a self-review, not an independent one.** No second agent
or human reviewed this brief. Treat its verdict as "the author tried to falsify his own
plan", not as peer approval.

Three challenges raised against the brief, and their resolution:

1. *"Normalizing response shapes hides a real server change from the caller — is that not
   the client lying about what it received?"* Partly fair. Resolved in DESIGN by making
   normalization strictly **additive**: the server's own keys are never removed or
   rewritten, so a caller who wants the raw truth still has it. The client adds the
   spelling it documents; it does not subtract the spelling the server sent.
2. *"Two lines is a policy assertion, not a finding. Why not one, or three?"* Two is
   retained from the existing README policy rather than re-derived, because the brief's job
   is to make the policy executable, not to relitigate it. What is new is the requirement
   that the oldest line's continued support be an explicit recorded decision rather than an
   omission — see SPECS R7.
3. *"The stale-pins problem and the multi-version problem are separable; bundling them
   widens the change."* Accepted as a risk and kept bundled anyway: the pins are stale
   **because** there is no single source and no procedure, so fixing the versions without
   fixing the mechanism reproduces the same drift by the next minor release.

## 7. Open items

- ~~Which patch of each line is current?~~ Resolved in RESEARCH §1: 9.4.5 and 9.5.2,
  from the live registry tag list on 2026-08-21.
- ~~Is `queries` in a stream upsert rejected on 9.5, or was the earlier finding an artifact
  of a malformed body?~~ Resolved in RESEARCH §3: rejected, reproduced against a valid body.
