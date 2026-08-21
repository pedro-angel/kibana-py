# Evidence — cloud environment battle test (9.5.1 vs 9.4.3)

**Date:** 2026-08-20
**Machine:** the x86_64 cloud session VM (Claude Code cloud environment).
**Commit under test:** `f1a8058` on branch `claude/cloud-environment-battle-test-cgq6ea`
(tree `0436f590`). The run itself executed `0bce59a`, which carried an identical tree and was
later rewritten message-only to strip a trailer, so the code measured here is byte-for-byte
the code at `f1a8058`.

## Why

`docs/source/development/cloud-environment.md` carried a `Status: partially verified` warning
with two open items: that the stack reaches `kibana=available` on 4 vCPUs, and that
`tests/integration/` runs against it. This run executes that page's own eight-step verification
list end to end, on both pinned stack versions, and diffs the two JUnit reports.

Nothing was fixed in this pass. Integration failures against 9.5.1 are the deliverable, not a
defect list to burn down: read them, do not fix them here.

## Machine

| | |
|---|---|
| Role | the x86_64 cloud session VM |
| Arch / kernel | `x86_64`, Linux 6.18.5-fc-v20 (Firecracker) |
| CPU / RAM | 4 vCPU / 15 GiB total (`free -h`) |
| Root filesystem | 252 G apparent, 17 G used, **21 G available** |
| Docker | Engine 29.3.1 (Community) |
| Python | CPython 3.11.15 |
| kibana-py | 0.5.0, installed `-e ".[async,orjson,observability]"` |

The disk figure is the one that matters: writable space is a fixed per-session allowance, so
`df`'s 252 G "Size" is not headroom. 21 G available is.

## Pre-flight — 4/4 PASS

### A. Docker daemon — PASS

```
$ docker info | head -3
Client: Docker Engine - Community
 Version:    29.3.1
 Context:    default
```

The `SessionStart` hook had already started it, and said so:
`[cloud-session-start] docker daemon already running`. The documented fallback
(`nohup dockerd > /tmp/dockerd.log 2>&1 &`) was not needed.

### B. Setup-script transcript — PASS

```
$ cat /var/log/kibana-py-cloud-setup.log
[cloud-setup] installing gh
[cloud-setup] apt-get update failed -- continuing without it
[cloud-setup] gh 2.45.0 installed
[cloud-setup] launching dockerd directly
[cloud-setup] docker daemon up (server 29.3.1)
[cloud-setup] pulling 9.5.1 images in parallel (210s of budget left)
[cloud-setup] pulling 9.4.3 images in parallel (163s of budget left)
[cloud-setup] cached 6 image(s); 0 left to pull on demand
[cloud-setup]   docker.elastic.co/kibana/kibana:9.5.1 (2.46GB)
[cloud-setup]   docker.elastic.co/elasticsearch/elasticsearch:9.5.1 (2.56GB)
[cloud-setup]   docker.elastic.co/apm/apm-server:9.5.1 (84.3MB)
[cloud-setup]   docker.elastic.co/kibana/kibana:9.4.3 (2.56GB)
[cloud-setup]   docker.elastic.co/apm/apm-server:9.4.3 (84.3MB)
[cloud-setup]   docker.elastic.co/elasticsearch/elasticsearch:9.4.3 (2.5GB)
[cloud-setup] finished in 98s (this transcript: /var/log/kibana-py-cloud-setup.log)
```

**The 210s budget clipped nothing.** Both version sets were pulled. The 9.5.1 wave started with
the full 210s and the 9.4.3 wave began with 163s still on the clock, so the 9.5.1 set cost **47s**;
the whole script — `gh`, daemon start, and both pull waves — finished in **98s**, well inside both
the 210s pull budget and the ~5 minute platform ceiling. `cached 6 image(s); 0 left to pull on
demand` is the script's own statement that nothing was deferred to session time.

`apt-get update failed` is expected and fail-open by design: the allowlist carries no Ubuntu
archive. `gh` still installed from the image's existing package cache.

On-disk confirmation, and the pinned digests every later step ran against:

```
$ docker system df
Images          6         3         9.939GB   5.018GB (50%)
```

| Image | Tag | Digest |
|---|---|---|
| `docker.elastic.co/elasticsearch/elasticsearch` | 9.5.1 | `sha256:b70b3017fbd35310bc57e7e3f8c0ca42ca0b94df3331f747b7cdcfddae430a5a` |
| `docker.elastic.co/kibana/kibana` | 9.5.1 | `sha256:f1e3cb03928b2c88590579445cd3ea3fad750a1b1ced653193ce4211051d2206` |
| `docker.elastic.co/apm/apm-server` | 9.5.1 | `sha256:b9c7704ec0b42bbfb0720bdbd4098bc6bc1bc02747aca9d088629670fa602af7` |
| `docker.elastic.co/elasticsearch/elasticsearch` | 9.4.3 | `sha256:851ff5f9615ab7d2f00931114f6db32850f0208ec9fe7e841f135ac78f5f13d5` |
| `docker.elastic.co/kibana/kibana` | 9.4.3 | `sha256:85e993bf4519827c84faa8a65265028d7ea572385f07ce8d913ad03025327ed7` |
| `docker.elastic.co/apm/apm-server` | 9.4.3 | `sha256:504abe10e8ebe56edb26bc6c11cfd72323b4a43fb8d9f43e6aa9d2df4ccf1db3` |

### C. Registry probe — PASS

```
$ docker pull docker.elastic.co/apm/apm-server:9.5.1
9.5.1: Pulling from apm/apm-server
Digest: sha256:b9c7704ec0b42bbfb0720bdbd4098bc6bc1bc02747aca9d088629670fa602af7
Status: Image is up to date for docker.elastic.co/apm/apm-server:9.5.1

real	0m1.388s
```

Resolve, authorize and blob-fetch all succeed. `docker-auth.elastic.co` is on the allowlist, which
is the part a `curl` against the registry cannot prove.

### D. Off-list host is refused — PASS (fails, as required)

```
$ curl -sS -o /dev/null -w '%{http_code}\n' https://example.com
curl: (56) CONNECT tunnel failed, response 403
000
$ echo $?
56
```

Refused at the proxy with `403`, exit 56. The environment is on the Custom allowlist, not Full
network access — so every allowlist result above means something.

## Environment findings — the VM itself

Two things about this VM that the cloud-environment page does not yet record. Both were found by
running, not by reading.

### Finding 1 — `memlock: -1` makes the stack un-startable here

The very first `ci-stack-up.sh` died in under a second:

```
$ ES_LOCAL_VERSION=9.5.1 ./scripts/ci-stack-up.sh
 Container kibana-py-es-local Starting
Error response from daemon: failed to create task for container: failed to create shim task:
OCI runtime create failed: runc create failed: unable to start container process:
error during container init: error setting rlimits for ready process:
error setting rlimit type 8: operation not permitted

real	0m0.595s
```

`rlimit type 8` is `RLIMIT_MEMLOCK`. The session VM drops the capability needed to raise it and
pins the hard limit at 8 MiB:

```
$ capsh --print | grep Current:
Current: =ep cap_sys_resource-ep      # CAP_SYS_RESOURCE explicitly dropped

$ prlimit --memlock
RESOURCE DESCRIPTION                           SOFT    HARD UNITS
MEMLOCK  max locked-in-memory address space 8388608 8388608 bytes
```

`elastic-start-local/docker-compose.yml` asks Elasticsearch for `memlock: {soft: -1, hard: -1}` —
unlimited — which requires `CAP_SYS_RESOURCE`. Isolated to that one setting, nothing else:

```
$ docker run --rm --ulimit memlock=-1:-1 docker.elastic.co/apm/apm-server:9.5.1 true
... error setting rlimit type 8: operation not permitted          # fails

$ docker run --rm --ulimit memlock=8388608:8388608 docker.elastic.co/apm/apm-server:9.5.1 sh -c ...
Error: unknown command "sh" for "apm-server"                       # container STARTED; app rejected argv
```

The second command reached the image's own entrypoint, so container init succeeded. The unlimited
request is the whole failure.

**Why it is safe to cap.** The compose file never sets `bootstrap.memory_lock=true`, so
Elasticsearch never attempts to lock its heap; the unlimited `memlock` is unused belt-and-braces
inherited from the upstream `start-local` template. Capping it to the VM's own hard limit changes
nothing Elasticsearch does.

**What this run did.** `soft`/`hard` were set to `8388608` **in the working tree only**, for the
duration of each `docker compose up`, and `git checkout --` restored the file immediately
afterwards. The change is **not committed** — the tree is clean at the commit that carries this
document, and `git status --porcelain` returned empty before it was written.

**Recommendation (not applied here).** A committed fix should not simply hard-code 8 MiB: GitHub
runners do grant `CAP_SYS_RESOURCE`, and `-1` is correct there. The portable form is to make the
value overridable, e.g. `memlock: {soft: ${ES_LOCAL_MEMLOCK:--1}, hard: ${ES_LOCAL_MEMLOCK:--1}}`
with the cloud environment setting `ES_LOCAL_MEMLOCK=8388608`. That is a change to
`elastic-start-local/` and CI behaviour, so it belongs in its own pass with its own review — not
smuggled into an evidence commit.

### Finding 2 — containers do not trust the agent proxy's CA, so Fleet cannot reach the registry

Kibana's Fleet plugin calls the Elastic Package Registry, and every such call failed:

```
[ERROR][plugins.fleet] Failed to fetch latest version of kbnpy_fleet_epm_432648df from registry:
  Error connecting to package registry: request to
  https://epr.elastic.co/search?package=...&kibana.version=9.5.1&spec.min=2.3&spec.max=3.6
  failed, reason: self-signed certificate in certificate chain
```

Elasticsearch hits the same wall on the `.elser-2-elasticsearch` inference endpoint
(`javax.net.ssl.SSLHandshakeException: (certificate_unknown) PKIX path building failed`).

**This is a CA-trust problem, not an allowlist problem.** The distinction matters because it
points at a different fix, and the error message alone invites the wrong diagnosis: a host the
egress policy rejects fails with a `403` on `CONNECT` (as `example.com` does in pre-flight D),
never with a certificate error. A certificate error means the connection *was* allowed and the
proxy re-terminated TLS with its own CA — one the container does not carry. Confirmed directly:

```
$ docker run --rm --entrypoint curl $ES_IMAGE -sS https://epr.elastic.co/categories
... unable to get local issuer certificate                        # http=000

$ docker run --rm -v /root/.ccr/ca-bundle.crt:/tmp/ca.crt:ro --entrypoint curl $ES_IMAGE \
    -sS --cacert /tmp/ca.crt -o /dev/null -w '%{http_code}\n' https://epr.elastic.co/categories
200

$ curl -sS -o /dev/null -w '%{http_code}\n' https://epr.elastic.co/categories   # from the VM itself
200
```

`epr.elastic.co` is reachable, and is already listed in this repo's prescribed allowlist. The
session VM trusts the proxy CA at `/root/.ccr/ca-bundle.crt`; the stack containers do not, and
the agent-proxy README calls this out as a known limitation of running containers under it.

Two consequences, both measured below:

1. **Every Fleet/EPM test fails**, with `[502] Error connecting to package registry` or the
   downstream `[404] [tcp] package not installed or found in registry`.
2. **The suite is slower.** Each registry call waits out a TLS failure. Progress visibly stalls
   through the Fleet block while container CPU sits near idle.

**The fix (not applied here)** is to give the stack containers the CA, by mounting
`/root/.ccr/ca-bundle.crt` into the Kibana and Elasticsearch services and pointing
`NODE_EXTRA_CA_CERTS` (Kibana) and the JVM truststore (Elasticsearch) at it. That is a change to
`elastic-start-local/`, so it belongs in its own pass — and it only matters inside a proxied
environment like this one, not on a GitHub runner.

This is an environment property, not a client defect, and it applies **identically to both
versions** — which is exactly why the version-to-version diff below is still trustworthy: these
tests fail on 9.4.3 too, so they cancel.

## Method

Both versions were run through an identical protocol, in the order the task set: **9.5.1 first,
9.4.3 second**.

```bash
# 1. bring the stack up on the version under test
time ES_LOCAL_VERSION=<v> ./scripts/ci-stack-up.sh

# 2. independent readiness check
curl -s localhost:5601/api/status | jq -r '.status.overall.level'

# 3. headroom, sampled while the suite was running
free -h; df -h /; docker stats --no-stream

# 4. mint a real ES API key so the api-key auth tests exercise that path
export ES_LOCAL_API_KEY=$(curl -s -u elastic:kibana-py-es-dev \
  -XPOST localhost:9200/_security/api_key -H 'Content-Type: application/json' \
  -d '{"name":"kibana-py-cloud"}' | jq -r .encoded)

# 5. the suite
KIBANA_URL=http://localhost:5601 KIBANA_USERNAME=elastic KIBANA_PASSWORD=kibana-py-es-dev \
  pytest tests/integration/ -q --junitxml=/tmp/junit-<v>.xml

# 6. tear down only what this run started
cd elastic-start-local && docker compose -f docker-compose.yml -f docker-compose.apm.yml down -v
```

`ci-stack-up.sh` mints an API key itself only under GitHub Actions (it gates on `$GITHUB_ENV`), so
step 4 is the local stand-in; `tests/integration/utils.py` picks `ES_LOCAL_API_KEY` up as a
fallback. The key was minted fresh per version — an API key does not survive `down -v`.

Three deliberate choices, so the diff measures the stack version and nothing else:

- **Both versions got a fresh stack.** Volumes were removed with `down -v` between versions, so
  neither suite inherited the other's saved objects, rules or data streams. A first 9.5.1 attempt
  was abandoned partway and its stack destroyed rather than reused, because re-running against a
  dirtied stack would have made the comparison unfair.
- **`pytest-randomly` was deliberately not installed.** It is in the `dev` extra and randomizes
  order per run with a fresh seed. Under it, the two runs would collect in different orders and
  any order-dependent test would show up in the diff as a fake version difference. Without it,
  collection order is identical across both runs, so a difference in outcome is a difference in
  the server. The environment installed was
  `-e ".[async,orjson,observability]"` plus `pytest pytest-cov pytest-mock pytest-asyncio
  pytest-timeout`.
- **The suite ran unbounded.** No `--timeout` was passed, so a slow Fleet test is recorded as slow
  rather than converted into a timeout failure that would differ between runs.

## Run — 9.5.1

### Step 1 — `ci-stack-up.sh` — PASS

```
$ time ES_LOCAL_VERSION=9.5.1 ./scripts/ci-stack-up.sh
stack_version_override=9.5.1 (template pins 9.4.3)
...
compose_up_seconds=70
kibana=available apm_http=200

real	1m10.865s
$ echo $?
0
```

Exit **0**, and it reports **`kibana=available`** (with `apm_http=200`). The override path works:
the script noticed `ES_LOCAL_VERSION` disagreed with the `.env.example` pin and said so, rather
than silently starting 9.4.3.

Seventy seconds from nothing to a Kibana serving `available`, on 4 vCPUs, with images already
cached. This is the first of the two items the cloud-environment page listed as
"not yet demonstrated".

### Step 2 — independent readiness — PASS

```
$ curl -s localhost:5601/api/status | jq -r '.status.overall.level'
available
```

Elasticsearch confirms the version actually under test:

```
$ curl -s -u elastic:kibana-py-es-dev localhost:9200 | jq -r '.version.number, .version.lucene_version'
9.5.1
10.5.0
```

(Unauthenticated `/api/status` returns only the `status` key on 9.5.1 — `.version` is `null`
there, which is why the version came from Elasticsearch.)

### Step 3 — headroom under load — PASS

Sampled 38% of the way through the suite, not at idle:

```
$ free -h
               total        used        free      shared  buff/cache   available
Mem:            15Gi       4.7Gi       1.3Gi       4.8Mi       9.0Gi        10Gi

$ df -h /
Filesystem      Size  Used Avail Use% Mounted on
/dev/vda        252G   17G   21G  45% /

$ docker stats --no-stream
NAME                     CPU %     MEM USAGE / LIMIT     MEM %     NET I/O
kibana-py-kibana-local   0.65%     1.064GiB / 15.7GiB    6.78%     98.6MB / 153MB
kibana-py-apm-local      0.21%     11.84MiB / 15.7GiB    0.07%     146kB / 72.2kB
kibana-py-es-local       1.69%     2.805GiB / 15.7GiB    17.87%    150MB / 97.5MB
```

Per-container peaks across the run: Elasticsearch **2.81 GiB**, Kibana **1.62 GiB**, APM
**12 MiB** — summing those (they did not all peak at once) puts the stack's ceiling near
**4.4 GiB** against 15 GiB total. `free -h` never showed less than **10 GiB available**, with the
suite mid-flight. Disk did not move off 21 G available at any sample.

The CPU numbers are the interesting part. At steady state the containers are close to idle
(0.65% and 1.69%), which says the suite is **latency-bound, not CPU-bound** — 4 vCPUs are not the
constraint. Bring-up is the only genuinely CPU-hungry phase (Kibana peaked at 141% during plugin
init). Runtime is dominated by round-trips, and by the Fleet tests waiting out TLS failures
against a package registry whose certificate they cannot verify (Finding 2).

### Step 4 — API key — PASS

Minted, 60 characters, exported as `ES_LOCAL_API_KEY` for the suite.

### Step 5 — integration suite — FAIL (expected, and the point)

```
25 failed, 703 passed, 18 skipped, 31 warnings, 5 errors in 2614.37s (0:43:34)
```

Exit 1, **751 tests**, wall clock **43m34s**.

## Run — 9.4.3

### Step 1 — `ci-stack-up.sh` — PASS

```
$ time ES_LOCAL_VERSION=9.4.3 ./scripts/ci-stack-up.sh
...
compose_up_seconds=66
kibana=available apm_http=200

real	1m5.784s
$ echo $?
0
```

Exit **0**, **`kibana=available`**, 66s. No `stack_version_override` line this time, correctly:
9.4.3 is what `.env.example` already pins, so there was nothing to override.

### Step 2 — independent readiness — PASS

```
$ curl -s localhost:5601/api/status | jq -r '.status.overall.level'
available

$ curl -s -u elastic:kibana-py-es-dev localhost:9200 | jq -r '.version.number, .version.lucene_version'
9.4.3
10.4.0
```

### Step 3 — headroom under load — PASS

Sampled 19% into the suite:

```
$ free -h
               total        used        free      shared  buff/cache   available
Mem:            15Gi       5.3Gi       833Mi       4.8Mi       9.9Gi        10Gi

$ df -h /
/dev/vda        252G   17G   21G  45% /

$ docker stats --no-stream
NAME                     CPU %     MEM USAGE / LIMIT     MEM %     NET I/O
kibana-py-kibana-local   13.59%    1.637GiB / 15.7GiB    10.43%    8.28MB / 18.6MB
kibana-py-apm-local      0.19%     8.535MiB / 15.7GiB    0.05%     13.8kB / 13.3kB
kibana-py-es-local       14.75%    2.718GiB / 15.7GiB    17.31%    16.8MB / 7.88MB
```

Same picture as 9.5.1: ~4.4 GiB of stack, **10 GiB still available**, disk static at 21 G, CPU
nowhere near saturating 4 vCPUs.

### Step 4 — API key — PASS

Minted fresh (the 9.5.1 key did not survive `down -v`), 60 characters.

### Step 5 — integration suite — FAIL (baseline)

```
16 failed, 712 passed, 18 skipped, 31 warnings, 5 errors in 2568.62s (0:42:48)
```

Exit 1, **751 tests**, wall clock **42m48s** — within 46 seconds of the 9.5.1 run, which is
consistent with both being dominated by the same registry-timeout stalls rather than by anything
version-specific.

## Step 6 — teardown

`docker compose -f docker-compose.yml -f docker-compose.apm.yml down -v` was run in
`elastic-start-local/` after each version, and again after the follow-up probe below.

```
$ docker ps -aq | wc -l        # 0
$ docker volume ls -q | wc -l  # 0
$ docker images | wc -l        # 6 — the cached set, untouched
```

Only what this run started was removed. The six pre-pulled images belong to the environment cache
and were deliberately left in place; they hold no state.

## The deliverable — diff of the two JUnit reports

```
9.4.3: total=751 passed=712 failed=16 error=5 skipped=18 wall=2568.6s
9.5.1: total=751 passed=703 failed=25 error=5 skipped=18 wall=2614.4s
```

| | 9.4.3 | 9.5.1 | Δ |
|---|---:|---:|---:|
| collected | 751 | 751 | 0 |
| passed | 712 | 703 | **−9** |
| failed | 16 | 25 | **+9** |
| errors | 5 | 5 | 0 |
| skipped | 18 | 18 | 0 |
| wall clock | 42m48s | 43m34s | +46s |

The two runs collected the **same 751 tests** and differ by exactly nine outcomes. Reading the
diff in both directions:

- **PASS on 9.4.3 → not PASS on 9.5.1: 9**
- **not PASS on 9.4.3 → PASS on 9.5.1: 0**
- PASS → SKIPPED: 0 · only in one report: 0

Zero test-set drift and zero improvements means the nine are a clean regression set, not
collection noise.

The 21 tests that fail or error on **both** versions (16 failures + 5 errors, identical on each
side) are entirely the package-registry casualties of Finding 2 — every one of them carries a
registry or "package not found" message on 9.4.3 as well:

| File | Count |
|---|---:|
| `test_fleet_epm_integration.py` | 15 |
| `test_fleet_policies_integration.py` | 5 (setup errors) |
| `test_entity_analytics_integration.py` | 1 |

Because they fail identically on both sides they cancel in the diff, and none of them appears in
the nine below.

### The nine

```
tests/integration/test_dashboards_integration.py
  TestDashboardsSearch::test_search_with_query_filter          KeyError: 'total'
  TestDashboardsSearch::test_search_with_tags_filter           KeyError: 'total'
  TestDashboardsSearch::test_search_with_excluded_tags_filter  KeyError: 'total'
  TestDashboardsSearch::test_search_pagination                 KeyError: 'page'
  TestDashboardsSpaceScoped::test_space_scoped_roundtrip       KeyError: 'total'
  TestAsyncDashboardsIntegration::test_async_crud_roundtrip    KeyError: 'total'

tests/integration/test_streams_integration.py
  TestStreamsLifecycle::test_upsert_wired_child_stream         BadRequestError [400] unrecognized_keys
  TestStreamsQueries::test_significant_events_read_and_preview AssertionError
  TestStreamsQueries::test_generate_significant_events_...     NotFoundError [404]
```

## Compatibility findings — what changed in 9.5.1

### Finding 3 — `GET /api/dashboards` was rewrapped in a `{data, meta}` envelope

Six of the nine are one root cause. To pin it rather than infer it from `KeyError`, the same
request was issued against both versions live:

```
$ curl -s -u elastic:… 'localhost:5601/api/dashboards?per_page=2&page=1'
```

| Version | Top-level keys | Body |
|---|---|---|
| 9.4.3 | `dashboards`, `page`, `total` | `{"dashboards":[],"page":1,"total":0}` |
| 9.5.1 | `data`, `meta` | `{"data":[],"meta":{"total":0,"page":1,"per_page":2}}` |

The list itself moved from `dashboards` to `data`, and the pagination counters moved from the top
level into a nested `meta` object — which additionally now reports `per_page`.

This lands directly on the documented contract of `client.dashboards.get_all()`. Its own docstring
promises the 9.4.3 shape:

```python
>>> results = client.dashboards.get_all(query="sales*", tags=[...], per_page=10, page=1)
>>> print(results.body["total"])
>>> for item in results.body["dashboards"]:
```

On 9.5.1 both of those raise `KeyError`; the equivalents are `results.body["meta"]["total"]` and
`results.body["data"]`. The client passes the response through untouched, so **every caller of
`dashboards.get_all()` breaks on 9.5.1**, sync and async alike — `test_async_crud_roundtrip` fails
the same way, confirming it is transport-independent. The Dashboards API is marked "Technical
preview in 9.4" in the client's own docstrings, so an unannounced envelope change is in-character
for its stability level.

### Finding 4 — Streams moved significant-events queries off the stream object

The remaining three are a second coherent change, in two halves.

**Write path — `queries` is no longer accepted in a stream upsert.**

```
kibana.exceptions.BadRequestError: [400] [
  { "code": "unrecognized_keys", "keys": ["queries"],
    "message": "Excess keys are not allowed", "path": [] } ]
```

9.4.3 accepted `queries` in the upsert body; 9.5.1 rejects it outright as an excess key.

**Read path — the response key was renamed `significant_events` → `queries`.** From the 9.5.1
assertion, which prints the body it actually received:

```
AssertionError: assert 'significant_events' in
  {'queries': [{'id': 'kbnpy-streams-sig', 'type': 'match', 'title': 'kbnpy significant', ...}],
   'aggregated_occurrences': []}
```

`aggregated_occurrences` survives; `significant_events` is now `queries`. This contradicts
`streams.get_significant_events()`'s stated return contract ("ObjectApiResponse with
`significant_events` … and `aggregated_occurrences`").

The third test, `test_generate_significant_events_requires_ai_connector`, fails with a bare
`[404] Not Found` on 9.5.1 where 9.4.3 answered — consistent with the generate endpoint having
moved or been re-pathed as part of the same reorganisation, though this run did not isolate its
new location.

Taken together the direction is legible: significant-events queries stopped being a property of
the stream document and became their own thing, and `queries` is now the name on the read side
rather than the write side.

## Scorecard

| Step | 9.5.1 | 9.4.3 |
|---|---|---|
| Pre-flight A — docker daemon | PASS | — |
| Pre-flight B — setup log / budget | PASS (6 cached, 0 clipped, 98s) | — |
| Pre-flight C — registry pull | PASS | — |
| Pre-flight D — off-list host refused | PASS (403, exit 56) | — |
| 1 — `ci-stack-up.sh` exit code | PASS (0) | PASS (0) |
| 1 — reports `kibana=available` | PASS | PASS |
| 2 — `/api/status` overall level | PASS (`available`) | PASS (`available`) |
| 3 — headroom under load | PASS (10 GiB free, 21 G disk) | PASS (10 GiB free, 21 G disk) |
| 4 — API key minted | PASS | PASS |
| 5 — `tests/integration/` | FAIL — 25F/703P/18S/5E, 43m34s | FAIL — 16F/712P/18S/5E, 42m48s |
| 6 — teardown | PASS | PASS |

Both step-5 FAILs are expected and are the deliverable, not a defect in the environment.

## What this settles about the environment

The cloud-environment page listed two things as "not yet demonstrated". Both are now demonstrated:

- **The stack reaches `kibana=available` on 4 vCPUs** — twice, in 70s and 66s, from cached images.
- **`tests/integration/` runs against it** — 751 tests collected and executed to completion on
  each version, 703 and 712 passing.

Measured against the page's stated ceilings: 15 GiB total RAM (page says ~16 GB) with the stack
peaking near 4.4 GiB and never dropping below 10 GiB available; 21 G of writable disk available
(the page says ~30 GB — this is the figure to correct, and the per-session allowance means `df`'s
252 G "Size" column is meaningless here); 4 vCPUs, which the suite never saturates.

Two caveats the page does not yet carry, both above: `memlock: -1` cannot be granted here
(Finding 1), and the stack containers do not trust the agent proxy's CA, which fails every
Fleet/EPM test and slows the suite (Finding 2). Neither is a client defect.

## Verdict

**The environment works, and the run produced a real compatibility finding.**

Pre-flight passed 4/4. Both stacks came up in about a minute and served `available`. The full
integration suite ran to completion twice, on a fresh stack each time, with identical collection
order — so the diff measures the server version and nothing else.

**Nine tests pass on Kibana 9.4.3 and fail on 9.5.1, with none failing the other way.** They
reduce to two server-side contract changes that `kibana-py` 0.5.0 does not yet handle:

1. `GET /api/dashboards` returns `{data, meta{total, page, per_page}}` on 9.5.1 instead of
   `{dashboards, page, total}` — breaking `dashboards.get_all()` for every caller, sync and async.
2. Streams significant-events queries moved off the stream upsert body (`queries` now rejected as
   an excess key) and the read envelope renamed `significant_events` to `queries`.

Both are reported here as measurements only. Nothing under `kibana/` was touched, no test was
edited, and no fix was attempted in this pass.

## Reproducing

```bash
# pre-flight
docker info | head -3
cat /var/log/kibana-py-cloud-setup.log
docker pull docker.elastic.co/apm/apm-server:9.5.1
curl -sS -o /dev/null -w '%{http_code}\n' https://example.com   # must fail

# per version, 9.5.1 then 9.4.3
time ES_LOCAL_VERSION=<v> ./scripts/ci-stack-up.sh
curl -s localhost:5601/api/status | jq -r '.status.overall.level'
free -h; df -h /; docker stats --no-stream
export ES_LOCAL_API_KEY=$(curl -s -u elastic:kibana-py-es-dev \
  -XPOST localhost:9200/_security/api_key -H 'Content-Type: application/json' \
  -d '{"name":"kibana-py-cloud"}' | jq -r .encoded)
KIBANA_URL=http://localhost:5601 KIBANA_USERNAME=elastic KIBANA_PASSWORD=kibana-py-es-dev \
  pytest tests/integration/ -q --junitxml=/tmp/junit-<v>.xml
(cd elastic-start-local && docker compose -f docker-compose.yml -f docker-compose.apm.yml down -v)
```

On this VM, `ci-stack-up.sh` needs Finding 1's `memlock` cap applied to
`elastic-start-local/docker-compose.yml` first, or it exits non-zero in under a second.
