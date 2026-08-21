# Evidence — multi-version support on Kibana 9.4.5 and 9.5.2

**Date:** 2026-08-21
**Machine:** the x86_64 cloud session VM (Claude Code cloud environment).
**Commit under test:** `1d3a8fb` (tree `f93fc01`), on branch
`claude/kibana-multi-version-sdd-rx4a3a`. Both full runs below executed that exact
tree with a clean working directory, recorded by the runner in each run's `.meta`.
Commits after it on the branch add this file and documentation only.

## Why

`README.md` claimed two supported Kibana lines and the client worked on one: nine
integration tests passed on 9.4 and failed on 9.5, measured on 2026-08-20 and recorded in
[`cloud-environment-battle-test.md`](cloud-environment-battle-test.md). Three things had
to be established before that claim could be made true:

1. what actually differs between the two lines — measured against running servers, not
   read from release notes;
2. that the client now behaves identically on both;
3. that neither line regressed on the way.

The pins are the latest patch of each supported line, confirmed against the Elastic
container registry rather than assumed.

## Machine

| | |
|---|---|
| Role | the x86_64 cloud session VM |
| CPU / RAM | 4 vCPU / 15 GiB (9.1 GiB available under a running stack) |
| Writable disk | ~21 GiB allowance; 11 GiB free with two version sets of images cached |
| Docker | Engine 29.3.1 |
| Python | CPython 3.11.15, `pip install -e ".[dev,all]" --ignore-installed` |
| Stack | `./scripts/ci-stack-up.sh`, one version at a time, volumes destroyed between |

## Method

```bash
# per version
docker compose -f docker-compose.yml -f docker-compose.apm.yml down --volumes
ES_LOCAL_VERSION=<pin> ./scripts/ci-stack-up.sh

python3 -m pytest tests/integration/ \
  -o addopts="" -p no:randomly -p no:cacheprovider \
  --timeout=180 --timeout-method=signal -q -ra --junitxml=<report>
```

with `KIBANA_URL=http://localhost:5601`, `KIBANA_USERNAME=elastic`,
`KIBANA_PASSWORD=kibana-py-es-dev`, and an `ES_LOCAL_API_KEY` minted per run so the
api-key auth tests exercise a real key. Volumes are destroyed between versions, so no
index, saved object or stream survives from one line into the other.

## 1. The pins were stale — established from the registry, not from memory

```
$ TOKEN=$(curl -sS "https://docker-auth.elastic.co/auth?service=token-service\
&scope=repository:kibana/kibana:pull" | jq -r .token)
$ curl -sS -H "Authorization: Bearer $TOKEN" \
    "https://docker.elastic.co/v2/kibana/kibana/tags/list" | jq -r '.tags[]' | grep -E '^9\.[45]\.'
9.4.0 9.4.1 9.4.2 9.4.3 9.4.4 9.4.5
9.5.0 9.5.1 9.5.2
```

The repository was pinned to 9.4.3 and 9.5.1 — two patches and one patch behind a policy
that reads "the latest patch of each". `elasticsearch/elasticsearch` and `apm/apm-server`
carry the same tags, and the `kibana:9.4.5` and `kibana:9.5.2` manifests both resolve
(`HTTP 200`), so both are pullable rather than merely listed. No `9.6.x` tag exists, so
the two most recent minor lines are still 9.5 and 9.4 and the oldest supported line stays
9.4 — recorded as a deliberate `kept` verdict in `SUPPORT_DECISIONS`, not left implicit.

## 2. What differs between the lines — four findings, all measured live

### Finding 1 — `GET /api/dashboards` was rewrapped

Same request, both servers:

| Version | Top-level keys | Body (empty page) |
|---|---|---|
| 9.4.5 | `dashboards`, `page`, `total` | `{"dashboards":[],"page":1,"total":0}` |
| 9.5.2 | `data`, `meta` | `{"data":[],"meta":{"total":0,"page":1,"per_page":2}}` |

The list moved from `dashboards` to `data`; the counters moved into `meta`, which also
reports `per_page` (9.4 does not report it at all). With a dashboard present the per-item
envelope is `{id, data, meta}` on both, so the difference is purely the outer wrapper.
This is the root cause of six of the nine pre-existing failures.

### Finding 2 — the stream upsert body: the two lines contradict each other

The finding that changed the design. Both servers, same matrix, every body carrying the
`stream.type` discriminator both lines require:

| Body | 9.4.5 | 9.5.2 |
|---|---|---|
| `dashboards:[], queries:[], rules:[]` | **200** | **400** `unrecognized_keys: ["queries"]` |
| `dashboards:[], rules:[]` (no `queries`) | **400** — `queries` required | **200** |
| `dashboards:[], queries:[]` (no `rules`) | 400 — `rules` required | 400 — `rules` required |
| `queries:[], rules:[]` (no `dashboards`) | 400 — `dashboards` required | 400 — `dashboards` required |
| `stream` alone | 400 — all three required | 400 — `dashboards`, `rules` required |

**No body satisfies both lines.** 9.4.5 requires `queries`; 9.5.2 rejects it. `dashboards`
and `rules` are required by both, so exactly one field is contested.

This refuted the working assumption. An earlier draft treated the field as version-free —
"send only what the caller passed" — which satisfies 9.5 and **fails every stream upsert
on 9.4**. It is now the one request in the client that depends on the server version, and
the only reason the taxonomy needs a third mechanism at all.

### Finding 3 — significant events renamed one response key

| Version | Top-level keys |
|---|---|
| 9.4.5 | `significant_events`, `aggregated_occurrences` |
| 9.5.2 | `queries`, `aggregated_occurrences` |

Per-entry fields are otherwise the same on both (`id`, `title`, `description`, `esql`,
`stream_name`, `occurrences`, `change_points`, `rule_backed`); 9.5 adds `type`. Additions
break nothing, so the rename is the whole difference.

A gating condition worth recording, because it produces a misleading symptom: on 9.5.2 the
significant-events routes answer `403` (`Significant events is disabled. Enable
"observability:streamsEnableSignificantEvents"…`) until that advanced setting is on. A
probe run without it produces `404`s that look exactly like Finding 4.

### Finding 4 — two endpoints were removed, not moved

With the setting **on** and a real child stream:

```
                                          9.5.2               9.4.5
POST …/significant_events/_generate  ->   404 Not Found       400 "No connector ID provided
                                                              and no default AI connector
                                                              configured"
POST …/significant_events/_preview   ->   404 Not Found       400 (schema error from a
                                                              deliberately incomplete probe
                                                              body — the route parsed it)
```

The 9.4.5 column is what makes the 9.5.2 column mean *removed* rather than *misdirected*:
same client, same paths, same feature flag, and 9.4.5 answers from inside the handler
while 9.5.2 has no route to answer at all.

Confirmed independently from the running server's own route registrations:

```
$ docker exec <kibana> sh -c "grep -rhoE \
    '/[a-zA-Z0-9_/{}.-]*significant_events[a-zA-Z0-9_/{}.-]*' \
    /usr/share/kibana/node_modules/@kbn/ | sort -u"
```

On 9.5.2 the only public significant-events route is
`GET /api/streams/{name}/significant_events`. There is no `_generate` and no `_preview`
under `/api/` anywhere in the installed code. The feature moved into a new
`@kbn/significant-events-plugin` whose surface is entirely `/internal/…` — a different
model (discoveries and detections), not a rename, so there is no public path to re-point
at. The public query-management routes the client already uses
(`GET|POST /api/streams/{name}/queries…`) survive on both lines.

The prior evidence recorded only `_generate` and guessed it had "moved or been re-pathed".
Both halves of that are corrected here.

## 3. The runs

Four full runs of `tests/integration/`. The first two bracket the change on 9.5.2; the
last two are the certification runs, both at commit `1d3a8fb`.

| # | Kibana | Code | Result | Wall |
|---|---|---|---|---|
| A | 9.5.2 | before the fix¹ | **9 failed**, 724 passed, 18 skipped | 21m50s |
| B | 9.5.2 | after the fix, interim | 748 passed, 0 failed, 18 skipped | 20m13s |
| C | 9.4.5 | `1d3a8fb` | **747 passed, 0 failed, 0 errors**, 19 skipped | 20m27s |
| D | 9.5.2 | `1d3a8fb` | **748 passed, 0 failed, 0 errors**, 18 skipped | 22m53s |

¹ Run A executed with the compatibility module present but wired into no endpoint, so the
behaviour it measures is the behaviour on `main`.

### The deliverable — run A against run B, on the same server

```
A: total=751 passed=724 failed=9 error=0 skipped=18 wall=1309.5s
B: total=766 passed=748 failed=0 error=0 skipped=18 wall=1213.0s
```

Nine outcomes changed, all in the same direction, and **zero regressions**:

```
failed -> passed  test_dashboards_integration.TestDashboardsSearch::test_search_with_query_filter
failed -> passed  test_dashboards_integration.TestDashboardsSearch::test_search_with_tags_filter
failed -> passed  test_dashboards_integration.TestDashboardsSearch::test_search_with_excluded_tags_filter
failed -> passed  test_dashboards_integration.TestDashboardsSearch::test_search_pagination
failed -> passed  test_dashboards_integration.TestDashboardsSpaceScoped::test_space_scoped_roundtrip
failed -> passed  test_dashboards_integration.TestAsyncDashboardsIntegration::test_async_crud_roundtrip
failed -> passed  test_streams_integration.TestStreamsLifecycle::test_upsert_wired_child_stream
failed -> passed  test_streams_integration.TestStreamsQueries::test_significant_events_read_and_preview
failed -> passed  test_streams_integration.TestStreamsQueries::test_generate_significant_events_requires_ai_connector
```

The 15 tests collected only in B are the new `test_version_compat_integration.py`; every
one passes. Nothing went `passed -> failed`, `passed -> skipped`, or disappeared from
collection.

The nine are the same nine the 2026-08-20 run found against 9.5.1, so **9.5.1 → 9.5.2
introduced no new divergence**, and no divergence exists outside the two features above —
bounded, as always, by what 610 endpoints' worth of live assertions actually touch.

### Runs C and D — the certification pair

Runs C and D are the claim. Same commit, same suite, one server version apart:

```
C (9.4.5): total=766 passed=747 failed=0 error=0 skipped=19 wall=1226.6s   exit=0
D (9.5.2): total=766 passed=748 failed=0 error=0 skipped=18 wall=1372.7s   exit=0
```

The two runs **collect the same 766 tests** and differ by **exactly one outcome**:

```
skipped -> passed   test_version_compat_integration.TestRemovedCapabilities
                    ::test_the_error_names_where_the_capability_does_exist
```

That one is the deliberate skip: on 9.4 the endpoint is routed, so there is no refusal
whose message could be checked. Nothing else differs — not a failure, not an error, not a
collection difference, in either direction.

This is the strongest form the claim takes. "The client behaves the same on both lines" is
not an argument from the design here; it is 765 identical outcomes out of 766, with the
single exception being a test that exists precisely to assert a difference.

Both runs exited `0`. The runner recorded `commit=1d3a8fb…`, `tree=f93fc01…` and
`dirty_paths=0` for each before starting, so neither measured an uncommitted tree.

### Skips, and why each is not a hole

Every skip carries a stated reason. Grouped:

Counted from the 9.4.5 run's 19 skips (9.5.2 has the same 18, minus the deliberate one):

| Count | Reason | Kind |
|---|---|---|
| 10 | No OTLP endpoint configured for that selection | test-selection choice |
| 4 | No live LLM connector on the stack — `converse`, `.gen-ai`, attack discovery, and the consumption backing index that only exists once a conversation has been persisted | missing infrastructure, named |
| 3 | ELSER-2 inference unavailable: Elasticsearch does not trust the egress proxy's CA | documented environment constraint |
| 1 | Agent Builder plugins API is feature-flag gated off on a default install | server configuration |
| 1 (9.4.5 only) | `the endpoint is routed on 9.4; nothing to refuse` | **deliberate** |

The last one is the only skip this change introduces, and it is the correct behaviour: it
guards an assertion that only means something on a line lacking the endpoint. Its sibling
tests do not skip on either line — they drive the real route on both and assert either the
server's own semantic rejection or the client's typed refusal.

The three ELSER skips are the known, documented constraint of this environment
(Elasticsearch's JVM truststore does not carry the egress proxy's CA — see
`docs/source/development/cloud-environment.md`); they are identical on both lines and
therefore cancel in any comparison between them.

## 4. What was corrected during this run, and why it is here

Two things that had nothing to do with Kibana versions surfaced, and both are recorded
because a run that hides its own mistakes is not evidence.

**Four self-inflicted errors, then a fix.** An earlier 9.4.5 run reported 4 errors, all
`Duplicate data view: kbnpy-dataviews test view`. Cause: the data-view fixture generated a
unique *id* but a fixed *name*, and Kibana rejects duplicates by name. A single leftover
view — from a run cancelled before its teardown ran — failed every test using that
fixture. The leftover was deleted, the fixture's name made unique (`1d3a8fb`), and run C
re-executed clean. A live gate that cannot survive its own interruption is a gate people
stop re-running.

**One pre-existing unit failure, unrelated to this work.**
`test_validate_apm_connectivity_reaches_ipv6_only_listener` fails on this VM, which has no
IPv6: `OSError: [Errno 97] Address family not supported by protocol`. Confirmed
pre-existing by running it on a pristine `main` checkout. The test already carried a
capability guard, but it began at `bind()` while the failure happens one line earlier, at
socket construction. The guard now covers construction, so the host it was written to
excuse skips rather than fails.

## 5. Scorecard

| Claim | Verdict |
|---|---|
| 9.4.5 and 9.5.2 are the latest patch of their lines | **PASS** — registry tag list |
| The client behaves identically on both lines | **PASS** — runs C and D |
| The 9.5 failures are fixed | **PASS** — 9 `failed -> passed`, run A vs B |
| Nothing on 9.4 regressed | **PASS** — run C, 0 failed, 0 errors |
| The removed endpoints raise, rather than 404 | **PASS** — asserted live on both lines |
| The contested upsert field works on both lines | **PASS** — asserted live on both lines |
| No divergence outside the two features | **MEASURED** — bounded by suite coverage |
| Every skip names its reason | **PASS** — table above |
| Both runs exercised the committed tree | **PASS** — `dirty_paths=0`, tree `f93fc01` in both `.meta` |

### What this does not establish

Stated so the scorecard is not read for more than it is worth.

- **Exhaustive API equivalence.** The suite exercises 610 endpoints, and no divergence
  appears in any of them, but a response field no assertion reads could still differ. That
  is why the version-support procedure requires a live run on every pin at every move,
  rather than trusting this result forward.
- **Other patches of either line.** 9.4.5 and 9.5.2 were measured; 9.4.0–9.4.4 and
  9.5.0–9.5.1 were not. The README says exactly that.
- **The three ELSER-dependent paths.** They skip on both lines for the documented
  Elasticsearch CA constraint of this environment, so this run says nothing about them
  either way.
- **The Python version matrix.** Certified separately by `make test-python-matrix`, not by
  these runs.

## 6. Reproducing

```bash
# whichever pin you want
docker compose -f elastic-start-local/docker-compose.yml \
               -f elastic-start-local/docker-compose.apm.yml down --volumes
ES_LOCAL_VERSION=9.4.5 ./scripts/ci-stack-up.sh   # or 9.5.2

export ES_LOCAL_API_KEY=$(curl -s -u elastic:kibana-py-es-dev \
  -XPOST localhost:9200/_security/api_key -H 'Content-Type: application/json' \
  -d '{"name":"kibana-py-local"}' | jq -r .encoded)

KIBANA_URL=http://localhost:5601 KIBANA_USERNAME=elastic \
KIBANA_PASSWORD=kibana-py-es-dev \
  python3 -m pytest tests/integration/ -o addopts="" -p no:randomly \
  --timeout=180 --timeout-method=signal -q -ra
```

`make versions` checks that every version statement in the repository still agrees with
`kibana/_compat.py`; `python3 scripts/checks/supported-versions.py --latest` asks the
registry whether these pins are still current.
