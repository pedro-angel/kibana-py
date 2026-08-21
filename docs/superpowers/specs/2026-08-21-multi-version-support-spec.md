# Multi-Version Kibana Support — Specification (the *what*)

**Date:** 2026-08-21
**Version:** v1.1
**Status:** Approved — reconciled onto delivered code (see §7 Reconciliation)
**Phase:** 3 of 5 (SPECS). Consumes:
[BRIEF](2026-08-21-multi-version-support-brief.md) and
[RESEARCH](../notes/2026-08-21-multi-version-support-research.md).
Feeds: [DESIGN](2026-08-21-multi-version-support-design.md).
**Review:** adversarial self-review, §8. Not an independent review.

This document states required behavior. It does not prescribe mechanism — that is
[DESIGN](2026-08-21-multi-version-support-design.md).

---

## 1. Vocabulary

| Term | Meaning here |
| :--- | :--- |
| **Line** | A Kibana minor series, e.g. `9.4.x`. |
| **Pin** | The exact patch of a line the repository provisions and tests, e.g. `9.4.5`. |
| **Supported set** | The lines the client claims to work against, each with its pin. |
| **Mirror** | Any file restating the supported set (a workflow matrix, a README table, an env template). |
| **Divergence** | A behavior difference between two supported pins, observed live. |

## 2. Requirements — client behavior

**R1. One contract across the supported set.**
For every public client method, a caller writing one piece of code against the documented
return contract gets the same result on every pin in the supported set. Where a server
renamed or rewrapped a response between lines, the client presents its documented spelling
on both.

**R2. Normalization is additive, never subtractive.**
The client MUST NOT remove, rename, or overwrite a key the server actually sent. It may only
add keys. A caller who wants exactly what the server returned can still read it. Where a key
the client would add is already present, the server's value wins.

**R3. Where the supported lines cannot agree on a request, the client sends what the
connected server accepts.**
Where one line requires a field that another rejects, no single body satisfies both, so the
client MUST choose by server version. Where the field is required it is supplied as before;
where it is not accepted it is omitted. A caller who explicitly supplied that field MUST NOT
have it silently dropped: the client refuses per R4 and names the portable alternative.

*Reconciled v1.0 → v1.1.* As first written, R3 said the client should simply stop sending a
contested field on the caller's behalf, on the belief that its absence satisfied every line.
The live 9.4.5 measurement (RESEARCH §3) refuted that: 9.4.5 **requires** `queries` in a
stream upsert body while 9.5.2 **rejects** it. Shipping the original R3 would have fixed 9.5
by breaking 9.4.

**R4. A capability absent from a supported line fails with a clear, typed error.**
Where an endpoint exists on one supported line and not another, calling it against the line
that lacks it MUST raise an error that names the method, the running server version, and the
lines on which the capability exists. A bare transport `404` is not acceptable: it is
indistinguishable from "you named a resource that does not exist".

**R5. The server version is observable.**
A caller can ask the client which Kibana it is connected to, and whether that version is in
the supported set, without hand-rolling a `/api/status` call. Determining it MUST NOT add a
request to any call path that does not need it, and a failure to determine it MUST NOT break
an otherwise valid call.

**R6. No silent behavior change on the older line.**
Every requirement above must leave the older supported line's observable behavior unchanged
except by addition. A caller upgrading the client while staying on the older Kibana sees no
removed key, no new exception on a call that previously succeeded, and no changed request
that the server previously accepted.

## 3. Requirements — the maintenance framework

**R7. The supported set is declared once, and the oldest line's place is a recorded decision.**

- One file is the source of truth for the supported set. Every mirror derives from it or is
  checked against it.
- Adding a line is a procedure, not an improvisation: pins move to the latest patch, the new
  line joins, and **the oldest line is explicitly re-decided** — kept or dropped, with the
  reason recorded and dated. Silence is not a decision; the gate must be unable to pass
  while the newest line is unrecorded.
- The decision has stated criteria, so two maintainers reach the same verdict.

**R8. Drift from the source of truth fails a gate.**
Editing a version string in a mirror without editing the source — or moving the source
without updating a mirror — MUST fail a check that runs in the local gate and in CI.

**R9. A newer upstream patch is detectable without reading release notes.**
A maintainer can ask, in one command, whether the pins are still the latest patch of each
supported line and whether a new line has appeared. Answering MUST consult the live registry,
not a hard-coded list.

**R10. Currency of the check is bounded by the network, not by silence.**
Where R9 cannot reach the registry, it reports that it could not check. It MUST NOT report
"up to date" from a failed lookup.

## 4. Requirements — verification

**R11. Both pins are tested live.**
The integration suite runs against a real Kibana at every pin in the supported set. A pin
that is only reasoned about is not supported.

**R12. The release gate blocks on every supported pin.**
A release cannot be cut while any pin in the supported set is red. A pin the release gate
does not exercise is not in the supported set — the set and the gate are the same list.

**R13. Divergences are recorded as evidence, not as prose.**
Each live run is captured as a committed artifact pinning the commands, the pins, the commit,
and the per-suite result.

## 5. Acceptance criteria

| # | Criterion | How it is checked |
| :-- | :--- | :--- |
| A1 | `dashboards.get_all()` exposes both the `dashboards`/`page`/`total` and `data`/`meta` spellings on every pin | unit tests both directions; integration assertion on both live pins |
| A2 | `streams.get_significant_events()` exposes both `significant_events` and `queries` on every pin | as A1 |
| A3 | `streams.upsert()` succeeds on every pin when the caller passes no `queries` | live integration test on both pins |
| A4 | `streams.upsert(queries=[...])` sends `queries` where the line accepts it, and raises rather than dropping it where it does not | unit tests asserting the transmitted body on each line |
| A5 | `streams.generate_significant_events()` and `preview_significant_events()` raise a typed, explanatory error on a pin that lacks the endpoint | unit test with a stubbed version; live integration test |
| A6 | `client.server_version` returns the running version and costs zero extra requests until first read | unit test counting transport calls |
| A7 | The supported set appears verbatim in exactly one source file | the drift gate enumerates mirrors |
| A8 | Editing any mirror alone fails `make versions` | gate exercised with a deliberate edit |
| A9 | `make versions --latest` reports a newer upstream patch when one exists | run live against the registry |
| A10 | The integration suite is green on both pins | committed evidence artifact |
| A11 | The release gate matrix equals the supported set | the drift gate reads the workflow |
| A12 | The version-support decision record names every line, its verdict, and a date | the drift gate refuses an undated or missing row |

## 6. Non-requirements

- The client does not translate between the two response *semantics* where a field's meaning
  changed rather than its name. No such case was found (RESEARCH §4); if one appears, it is a
  new spec, not an extension of R1.
- The client does not implement endpoints that exist on only one line beyond raising R4's
  error. Re-implementing 9.5's internal significant-events surface is out of scope per BRIEF §4.
- The drift gate does not edit mirrors. It reports; a human or a follow-up commit fixes.

## 7. Reconciliation onto delivered code

Recorded after the build, per the spec-driven-development rule that a spec describes what
shipped.

| Requirement | Delivered as | Divergence from the spec as first written |
| :--- | :--- | :--- |
| R1, R2 | `kibana/_compat.py` normalizers, applied in `dashboards.get_all()` and `streams.get_significant_events()` in both trees | none |
| R3 | `streams.upsert()` supplies `queries` on 9.4, omits it on 9.5, and refuses an explicit `queries` on 9.5 with a hint naming `upsert_query()` / `bulk_queries()` | R3 itself was rewritten — see its reconciliation note. The mechanism moved from request shaping to version gating, and `KibanaVersionError` gained an actionable `hint`. |
| R4 | `KibanaVersionError`, raised by the two removed-endpoint methods | the error type is new public API; the spec had not said whether to reuse an existing exception |
| R5 | `Kibana.server_version` / `AsyncKibana.server_version` | async could not be a property — it is an awaitable method there, so the two trees differ in call syntax. Recorded in DESIGN §4 and the README. |
| R6 | verified by the 9.4.5 live run | none |
| R7–R10 | `kibana/_compat.py` `SUPPORTED_VERSIONS` + `scripts/checks/supported-versions.py` + `make versions` | none |
| R11–R13 | both pins run live; `docs/evidence/multi-version-9.4.5-9.5.2.md` | none |

## 8. Adversarial self-review

**This is a self-review.** No independent reviewer saw this spec.

1. *"R1 and R2 conflict: you cannot present one contract without overwriting something."*
   They do not conflict, because the two spellings do not collide — measured in RESEARCH §2
   and §3, the 9.4 and 9.5 key sets are disjoint at every level the client normalizes. R2's
   "server wins on collision" clause covers the case where a future line reuses a name with a
   different meaning, which would be a semantic change and therefore out of scope per §6.
2. *"R4 requires knowing the server version, and R5 says determining it must not add a
   request. Those cannot both hold."* They hold together only because R5 says "any call path
   **that does not need it**". The gated methods do need it and pay for one lookup, once per
   client. Everything else pays nothing. The wording was tightened after this challenge.
3. *"R12 makes every release hostage to the older line."* That is the intent, and it is the
   point of R7's recorded decision: if blocking on the older line stops being worth it, the
   answer is to drop the line deliberately and record why — not to quietly stop testing it.
