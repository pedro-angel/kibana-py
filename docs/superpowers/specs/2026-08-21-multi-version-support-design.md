# Multi-Version Kibana Support — Design (the *how*)

**Date:** 2026-08-21
**Version:** v1.2
**Status:** Approved — reconciled onto delivered code (§8)
**Phase:** 4 of 5 (DESIGN). Consumes:
[SPECS](2026-08-21-multi-version-support-spec.md) and
[RESEARCH](../notes/2026-08-21-multi-version-support-research.md).
Feeds: [TASKS](../plans/2026-08-21-multi-version-support.md).
**Review:** adversarial self-review, §9. Not an independent review.

SPECS states *what* must hold. This document commits to *how*, and to the trade-offs
that choice accepts.

---

## 1. The shape of the problem

Three kinds of version difference exist between Kibana 9.4.5 and 9.5.2, and each
admits a different mechanism. Conflating them is what makes multi-version clients
turn into forked code paths.

```{mermaid}
flowchart TB
    diff["A difference between two supported lines"]
    diff --> q1{"Is it visible only<br/>in the RESPONSE?"}
    q1 -->|yes| norm["Normalize: add the missing spelling.<br/>Version-free — the shape is its own discriminator."]
    q1 -->|no| q2{"Does one line REJECT a request field<br/>the other REQUIRES?"}
    q2 -->|yes| shape["Gate the FIELD on the server version.<br/>No single body satisfies both."]
    q2 -->|no| q3{"Is the endpoint<br/>absent on one line?"}
    q3 -->|yes| gate["Gate on the server version.<br/>The ONLY mechanism that needs to know the version."]
    q3 -->|no| semantic["Semantic change — out of scope.<br/>New spec, not an extension of this one."]
```

The design's central claim, **as reconciled against the live measurement**: every
*response* difference is absorbed without knowing the server version, because the shape
discriminates itself; *request* differences are not, because the client must choose what to
send before the server can object.

An earlier draft of this document put the contested `queries` field in the second box, on
the belief that omitting it satisfied both lines. The 9.4.5 probe refuted that — 9.4.5
requires the field, 9.5.2 rejects it (RESEARCH §3) — so it moved to the third box. Two of
the four measured divergences need no version knowledge, and both are responses. The client
still has no version-branched *code path*: it has one version-dependent *field*, decided by
a table lookup, and two version-gated methods.

## 2. Component map

```{mermaid}
flowchart LR
    subgraph pkg["kibana/ (ships in the wheel)"]
        compat["_compat.py<br/>SUPPORTED_VERSIONS · SUPPORT_DECISIONS<br/>CAPABILITIES · normalizers · ServerVersionCache"]
        base["_sync/_base.py · _async/_base.py<br/>server_version()"]
        util["_sync/utils.py · _async/utils.py<br/>_require_capability()"]
        ns["dashboards.py · streams.py<br/>(both trees)"]
        compat --> base
        compat --> util
        util --> ns
        compat --> ns
    end
    subgraph gate["the gate (not shipped)"]
        script["scripts/checks/supported-versions.py"]
        mk["make versions"]
        dodc["dod.config: versions_consistent"]
        mk --> script
        dodc --> mk
    end
    subgraph mirrors["mirrors — derived or checked, never authored"]
        wf["integration-probe.yml · release.yml<br/>(matrix generated)"]
        env[".env.example · cloud-setup.sh"]
        docs["README · cloud-environment.md"]
    end
    compat -. "read with ast, no import" .-> script
    script --> mirrors
    compat -. "--matrix" .-> wf
```

## 3. Decision: response normalization is additive and bidirectional

**Mechanism.** `normalize_dashboards_search()` and `normalize_significant_events()`
are pure functions over the parsed body. Each adds the spelling that is missing and
returns the same object, mutated in place.

**Why bidirectional rather than "translate 9.5 back to 9.4".** A one-way translation
would make code written against the newer server's own documented shape fail on the
older one — the client would be fluent in exactly one direction, and a caller reading
Elastic's current API docs would write the shape that breaks. Adding both spellings
means one piece of caller code works on both lines *whichever* spelling the caller
picked up. The cost is two extra keys per response, aliased rather than copied.

**Why in place rather than reconstructing the response.** `ObjectApiResponse.body`
returns the same dict on every access, so mutating it is visible through the response
object with no reconstruction. Rebuilding the envelope would mean re-deriving `meta`,
and any field elastic-transport adds later would have to be threaded through by hand.

**Why additive is a hard rule, not a preference.** The client cannot know why a caller
reads a key. Removing `data` on 9.5 to "clean up" would break code that reads the
server's own documented shape; overwriting `total` with a derived value would make the
client the source of a number the server already stated. Both are the client lying
about what it received. The rule is enforced by unit tests that assert every original
key survives with its original value.

**Rejected alternative — normalize centrally in `perform_request()`.** It would catch
every endpoint at once, and it is wrong: `perform_request` does not know which
endpoint it just called, so it would have to sniff shapes. A body that happens to
carry `data` and `meta` for unrelated reasons would be silently rewritten. Endpoint
knowledge belongs at the endpoint.

## 4. Decision: the server version is resolved once, lazily, and never on the hot path

**Mechanism.** `BaseClient.server_version()` reads `version.number` from
`GET /api/status` on first call and caches it in a `ServerVersionCache` shared with
every `options()` clone — the same lifetime rule the space cache already uses, for the
same reason: a clone talks to the same server.

**Cost.** Zero for callers who never ask. One request, once per client, for those who
do. Nothing on any other call path.

**Sync/async asymmetry, accepted deliberately.** `server_version()` is a *method* in
both trees rather than a property, because the async version must be awaited and a
property cannot be. The two trees therefore read `client.server_version()` and
`await client.server_version()` — the same difference every other method in this
client already has. The alternative, a sync-only property plus an async-only method,
would have made the two trees diverge in *name*, which is worse than diverging in
`await`.

**No TTL.** A Kibana process does not change version under a live connection. Behind a
load balancer mid-rolling-upgrade two versions can answer; the cache holds whichever
replied first, which is also the only honest thing one string can say about that.

## 5. Decision: capability gating fails open, never closed

`_require_capability()` refuses a call **only** when it has positively established
that the connected server's line is supported and is known not to route the endpoint.
Every other case proceeds:

Capabilities are named the same way whether they are a whole method or a single request
field: `streams.preview_significant_events` and `streams.upsert.queries` are both rows in
`CAPABILITIES`, and both go through the same check. A field-level refusal carries a `hint`
naming what to use instead, because "not available here" without an alternative is barely
better than the error it replaced.

| Situation | Behavior | Why |
| :--- | :--- | :--- |
| Version resolved, line supported, capability absent | `KibanaVersionError` before any request | The one case the client can prove |
| Version resolved, line **not** in the supported set | proceed | The client has measured nothing about that server |
| `/api/status` errored or returned no version | proceed | A client that refuses calls because it could not introspect is worse than the 404 it was avoiding |
| Capability not in the table | proceed | The table records measured absences; silence means nothing was measured |

The failure direction matters more than the mechanism. A gate that fails closed turns
"I could not check" into "you may not call", which breaks working code on servers the
client was never asked to reason about. Failing open costs, at worst, the bare `404`
that was the pre-existing behavior.

## 6. Decision: one declared set, mirrors derived or checked

**The source** is `SUPPORTED_VERSIONS` in `kibana/_compat.py`. It ships in the wheel
because `is_supported()` is a runtime question, and it is read by the gate with
`ast.literal_eval` rather than an import, so a CI job can build a matrix on a bare
checkout with nothing installed.

**Mirrors are handled in one of two ways, never a third:**

- **Derived** — the two workflow matrixes call `supported-versions.py --matrix`. There
  is no version literal in them to drift, and the gate fails if one reappears.
- **Checked** — `.env.example`, `cloud-setup.sh`, the README table and the
  cloud-environment page state versions in prose or config that cannot be generated
  without making those files unreadable. `make versions` compares each against the
  source and names the file and the expected value on failure.

**Why not generate everything.** A README table assembled by a script is a README
nobody edits and everybody distrusts. Checking preserves the human-authored file and
still makes drift impossible to merge.

**The decision record is machine-checked.** `SUPPORT_DECISIONS` must carry a dated row
per supported line, and the *oldest* line's row must read `kept`, not `added`. That
single assertion is what makes "should the oldest version still be supported?" a
question the repository forces someone to answer: adding a new line while leaving the
oldest row as `added` fails the gate, and the only way to pass is to record a verdict.

## 7. What this design deliberately does not do

- **No re-pointing of removed endpoints at internal routes.** 9.5's replacement for
  significant-events generation lives under `/internal/significant_events/*`. Internal
  routes carry no compatibility promise; binding the client to them would trade a
  clear error for a silent break at the next patch.
- **No version-branched request builders.** Exactly one field in one request body varies
  by version, decided by a `CAPABILITIES` lookup rather than by an `if version` in the
  method. Everything else the client sends is identical on both lines.
- **No capability probing.** The client does not discover routes at runtime by trying
  them. The table is measured once, live, and recorded — probing would spend a request
  per call to re-derive a constant.

## 8. Reconciliation onto delivered code

| Design element | Delivered | Divergence |
| :--- | :--- | :--- |
| §3 normalizers | `kibana/_compat.py`, applied in `dashboards.get_all()` and `streams.get_significant_events()` in both trees | none |
| §4 `server_version()` | both `_base.py` trees, cache shared through `options()` | none |
| §5 `_require_capability()` | both `utils.py` trees; used by `streams.generate_significant_events` / `preview_significant_events` | none |
| §6 source + gate | `SUPPORTED_VERSIONS` + `scripts/checks/supported-versions.py` + `make versions` + `dod.config` | none |
| §6 derived matrixes | `integration-probe.yml`, `release.yml` both gained a `versions` job | the release gate became a matrix job, which also delivered SPECS R12 |
| request field gating | `streams.upsert()` decides the `queries` field by server version | **the design changed here.** It was drafted as version-free request shaping and reclassified as version gating after the 9.4.5 probe refuted the assumption behind it (RESEARCH §3). |

## 9. Adversarial self-review

**Self-review, not independent.** Three challenges:

1. *"Aliasing the same list under two keys will surprise someone who mutates one."*
   True, and accepted. Copying would decouple them, at the cost of duplicating every
   search page and creating a second, silently stale copy — a worse surprise. The
   aliasing is documented on both functions and asserted in the unit tests, so it is a
   stated property rather than an accident.
2. *"Failing open means a caller on an unsupported server still gets the bare 404 this
   was meant to fix."* Correct, and deliberate per §5. The client has measured nothing
   about unsupported servers; inventing an error message for one would be a claim it
   cannot support. The supported set is where the client's knowledge ends, and the
   gate's behavior ends there too.
3. *"Checking the README table with a regex is brittle — a formatting change breaks the
   gate."* Accepted. The failure mode is a loud, obvious gate failure naming the file,
   not a silent wrong answer, and the alternative (generating the table) costs more
   than it saves per §6. If the table is reformatted, the regex is a one-line fix and
   the gate is what tells you to make it.
