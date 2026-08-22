# Research — what actually differs between Kibana 9.4.5 and 9.5.2

**Date:** 2026-08-21
**Status:** research (measurement, not decision — decisions are in SPECS and DESIGN)
**Phase:** 2 of 5 (RESEARCH). Consumes:
[BRIEF](../specs/2026-08-21-multi-version-support-brief.md).
Feeds: [SPECS](../specs/2026-08-21-multi-version-support-spec.md) and
[DESIGN](../specs/2026-08-21-multi-version-support-design.md).
**Review:** adversarial self-review, §7. Not an independent review.

Every claim below was produced by a command run against a live server or a live registry,
and the command is shown. Where an inherited claim was checked and did **not** hold, that
is stated as prominently as the ones that did — the point of re-measuring is to find those.

Method note: the client's own OpenAPI-style route inventory was unavailable —
`GET /api/oas` answers `404` on 9.5.2 — so route existence was established two ways
instead: by driving the real HTTP route, and by reading the route registrations inside the
running Kibana container. Where the two agreed, the finding is called settled.

---

## 1. The pins were stale, and the policy names the wrong patches

The repository targeted 9.4.3 and 9.5.1. The registry that serves the stack images says
otherwise:

```
$ TOKEN=$(curl -sS "https://docker-auth.elastic.co/auth?service=token-service\
&scope=repository:kibana/kibana:pull" | jq -r .token)
$ curl -sS -H "Authorization: Bearer $TOKEN" \
    "https://docker.elastic.co/v2/kibana/kibana/tags/list" | jq -r '.tags[]' | grep -E '^9\.[45]\.'
9.4.0 9.4.1 9.4.2 9.4.3 9.4.4 9.4.5
9.5.0 9.5.1 9.5.2
```

The same tags exist for `elasticsearch/elasticsearch` and `apm/apm-server`, and the
manifests for `kibana:9.4.5` and `kibana:9.5.2` both resolve (`HTTP 200`), so both are
really pullable rather than merely listed.

Two consequences:

- **The pins move to 9.4.5 and 9.5.2.** The stated policy is "the latest patch of each",
  and the repository was two patches behind on one line and one on the other.
- **The supported lines do not change.** There is no `9.6.x` tag, so the two most recent
  minor lines are still 9.5 and 9.4. The oldest supported line stays 9.4 — and per BRIEF
  §2 that has to be a recorded decision rather than an omission, which it now is
  (`SUPPORT_DECISIONS` in `kibana/_compat.py`, and the table in the version-support page).

## 2. `GET /api/dashboards` — confirmed, and it is the largest divergence

Measured directly against each live server:

```
$ curl -s -u elastic:… 'localhost:5601/api/dashboards?per_page=2&page=1'
```

| Version | Top-level keys | Body |
| :--- | :--- | :--- |
| 9.4.5 | `dashboards`, `page`, `total` | `{"dashboards":[…],"page":1,"total":N}` |
| 9.5.2 | `data`, `meta` | `{"data":[…],"meta":{"total":N,"page":1,"per_page":2}}` |

The list was renamed `dashboards` → `data`; the counters moved from the top level into
`meta`, which additionally reports `per_page` (9.4 does not report it at all). With a
dashboard present, `data[0]` carries `id`, `data`, `meta` — the per-item envelope is
unchanged, so the difference is purely the outer wrapper.

This is what breaks six integration tests: the client passed the body through untouched,
so a caller reading `body["total"]` raised `KeyError` on 9.5.

## 3. Streams `queries` in a stream upsert — the inherited evidence was half the story

The prior evidence recorded that 9.5 "rejects `queries` as an excess key", and said
nothing about what 9.4 does without it. Both halves turned out to matter.

The first re-probe appeared to contradict even the recorded half: on 9.5.2 the upsert
failed with an `invalid_union` error naming `stream.type`, not `queries`, for **every**
body shape including one with no `queries` at all. That was a fault in the probe, not in
the finding — the probe body omitted the `type` discriminator that both lines require.

With a valid body, and the matrix run against **both** live servers:

```
$ curl -s -XPUT 'localhost:5601/api/streams/<child>' -d '<body>'
```


| Body (all with `stream.type = "wired"`) | 9.4.5 | 9.5.2 |
| :--- | :--- | :--- |
| `dashboards:[], queries:[], rules:[]` | **200** | **400** `unrecognized_keys: ["queries"]` |
| `dashboards:[], rules:[]` (no `queries`) | **400** — `queries` required | **200** |
| `dashboards:[], queries:[]` (no `rules`) | 400 — `rules` required | 400 — `rules` required |
| `queries:[], rules:[]` (no `dashboards`) | 400 — `dashboards` required | 400 — `dashboards` required |
| `stream` alone | 400 — all three required | 400 — `dashboards`, `rules` required |

**There is no body that both lines accept.** 9.4.5 *requires* `queries`; 9.5.2 *rejects*
it. `dashboards` and `rules` are required by both, so only this one field is contested.

This refuted the design's working assumption. An earlier draft classified the field as a
"send only what the caller passed" case — version-free, because omitting it was believed
to satisfy both. Omitting it satisfies 9.5 and **fails 9.4 with a 400 naming the field**.
The classification moved to version gating (`streams.upsert.queries` in `CAPABILITIES`),
and SPECS R3 and DESIGN §1 were reconciled to match. It is the only request in the client
that varies by server version.

The recorded reason mattered twice over. Had the probe's own `stream.type` error been
taken at face value, the conclusion would have been "9.5 changed the stream schema". Had
the 9.5-only measurement been generalised, every stream upsert would have broken on 9.4 —
a regression introduced by the fix for the other line, and exactly the failure mode that
measuring both lines rather than one exists to catch.

## 4. Significant events — the rename is confirmed, and the endpoint removal is worse
   than recorded

**The read envelope renamed one key.** On 9.5.2, with the feature enabled:

```
$ curl -s '…/api/streams/<child>/significant_events?from=…&to=…&bucketSize=1h'
{"queries":[{"id":"kbnpy-probe-q",…,"occurrences":[],"change_points":{…},
 "rule_backed":true}],"aggregated_occurrences":[]}
```

Top-level keys are `queries` and `aggregated_occurrences`. The same request against
9.4.5 returns `significant_events` and `aggregated_occurrences` — so exactly one key was
renamed, and `aggregated_occurrences` is unchanged:

| Version | Top-level keys |
| :--- | :--- |
| 9.4.5 | `significant_events`, `aggregated_occurrences` |
| 9.5.2 | `queries`, `aggregated_occurrences` |

Per-entry fields are the same on both (`id`, `title`, `description`, `esql`,
`stream_name`, `occurrences`, `change_points`, `rule_backed`); 9.5 adds `type`. Additions
break nothing, so the rename is the whole difference.

**A gating condition the inherited evidence did not name.** On 9.5.2 the significant-events
routes answer `403` until an advanced setting is switched on:

```
{"statusCode":403,"error":"Forbidden","message":"Significant events is disabled.
 Enable \"observability:streamsEnableSignificantEvents\" in Advanced Settings…"}
```

The integration suite already enables it (`test_streams_integration.py` owns that
enable/restore contract), which is why the suite saw `404`s rather than `403`s. It matters
here because the first probe, run without the setting, produced `404`s that could have
been mistaken for the endpoint removal below.

**`_generate` and `_preview` are both gone from the public API — not just `_generate`.**
With the setting **on**, and a real stream:

```
                                          9.5.2                 9.4.5
POST …/significant_events/_generate  ->   404 Not Found         400 "No connector ID
                                                                provided and no default
                                                                AI connector configured"
POST …/significant_events/_preview   ->   404 Not Found         400 (schema error from a
                                                                deliberately incomplete
                                                                probe body — the route
                                                                parsed the request)
```

The 9.4.5 column is what makes the 9.5.2 column mean "removed" rather than "misdirected":
the same client, the same paths, the same feature flag, and 9.4.5 answers from inside the
handler while 9.5.2 has no route to answer at all.

The inherited evidence recorded only `_generate`, and guessed it had "moved or been
re-pathed". Reading the running server's own route registrations settles both questions:

```
$ docker exec <kibana> sh -c "grep -rhoE '/[a-zA-Z0-9_/{}.-]*significant_events[a-zA-Z0-9_/{}.-]*' \
    /usr/share/kibana/node_modules/@kbn/ | sort -u"
```

On 9.5.2 the **only** public significant-events route is
`GET /api/streams/{name}/significant_events`. There is no `_generate` and no `_preview`
under `/api/` anywhere in the installed code. Significant events moved into a new
`@kbn/significant-events-plugin`, whose surface is entirely internal:

```
GET  /internal/significant_events/{availability,detections,discoveries,events}
POST /internal/significant_events/{detections,discoveries,events}
POST /internal/streams/significant_events/discovery/_execute
```

The public query-management routes that *did* survive are
`GET /api/streams/{name}/queries`, `PUT|DELETE /api/streams/{name}/queries/{queryId}` and
`POST /api/streams/{name}/queries/_bulk` — all of which the client already uses and which
work on both lines.

So this is a removal, not a rename: there is no public path to re-point at. The internal
replacement carries no compatibility promise and models the feature differently
(discoveries and detections rather than a one-shot generate), so binding a client to it
would trade a clear error for a silent break.

## 5. Nothing else diverges, measured rather than assumed

The strongest available instrument is the client's own integration suite, which exercises
610 endpoints across 39 namespaces. Run against live 9.5.2 before any change:

```
9 failed, 724 passed, 18 skipped in 1309.51s
```

The nine failures are exactly the nine that the 2026-08-20 run found against 9.5.1 — the
six dashboards-search tests and the three streams tests analysed above. **9.5.1 → 9.5.2
introduced no new divergence**, and no divergence exists outside the two features already
identified.

Two further observations from that run, neither a version difference:

- The 21 Fleet/EPM failures the earlier evidence recorded are **gone**. They were the
  package-registry casualties of the intercepted-egress constraint, fixed by the proxy-CA
  overlay that landed after that run. Their absence here is that fix confirmed live.
- Eighteen tests skip, on both lines, for stated environment reasons: no LLM connector, no
  OTLP endpoint configured for that selection, and ELSER-2 inference unavailable because
  Elasticsearch does not trust the egress proxy's CA (a documented, deliberate gap in
  `docs/source/development/cloud-environment.md`).

## 6. What the measurements imply for the design

Stated here as implications, not decisions — DESIGN commits.

| Divergence | Visible in | Can the client absorb it without knowing the version? |
| :--- | :--- | :--- |
| Dashboards search envelope | response only | **Yes** — the shape discriminates itself |
| Significant-events key rename | response only | **Yes** — same |
| `queries` in a stream upsert | request; **9.4 requires it, 9.5 rejects it** | **No** — no body satisfies both |
| `_generate` / `_preview` removed | route existence | **No** — nothing in the request or response reveals it before it fails |

Two of four need no version knowledge, and both of those are responses. The generalisation
that survives measurement is narrower than the one the design started with: *response*
differences are absorbable without knowing the version, because the shape discriminates
itself; *request* differences are not, because the client must choose what to send before
the server can object.

## 7. Adversarial self-review

**Self-review, not independent.**

1. *"A grep of a container's JavaScript is not proof that a route does not exist — routes
   can be assembled from constants."* Correct, and it is why the grep is not the only
   evidence. The route was also driven live, with the feature flag on, against a real
   stream, and answered `404`. The grep explains *why* (a new plugin owns the feature, and
   its surface is internal); the live probe establishes *that*. Either alone would be
   weaker than both together, and §4 is claimed only on the pair.
2. *"§5 concludes 'nothing else diverges' from a suite that cannot cover every endpoint's
   every response field."* Fair — the claim is bounded by what the suite exercises, and it
   is worded as such: no divergence appears in 610 endpoints' worth of live assertions.
   A field the suite never reads could still have changed. The honest statement is
   "measured, not proven exhaustively", which is why the supported set is re-measured live
   on every version move rather than trusted forward.
3. *"The `queries` re-probe found the earlier evidence right anyway — was re-measuring
   worth it?"* It did not, and this is the clearest case in the document. The inherited
   note was right that 9.5 rejects the field and silent about what 9.4 does with its
   absence; the 9.5-only measurement suggested a version-free fix; the 9.4.5 measurement
   refuted it outright. Re-measuring both lines — not just the new one — is what stopped
   a fix for 9.5 from becoming a regression on 9.4. That is the argument for the
   version-support procedure requiring a live run on **every** pin, not only the one that
   changed.
