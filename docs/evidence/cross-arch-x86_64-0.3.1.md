# Evidence — cross-architecture verification (x86_64 / Intel) for 0.3.1

The primary development host is Apple Silicon (arm64/macOS). To confirm the project also works
on Intel/AMD64, the exact `0.3.1` branch was built and tested end-to-end on an x86_64 Linux host.
Captured per `battle-testing-on-real-infra` — the running system is ground truth.

## Environment

- **Host:** dedicated x86_64 verification host — Debian GNU/Linux 13 (trixie), kernel 6.12, 4 CPU / 7.7 GB RAM / Docker.
- **Code under test:** the `feat/kibana-9.4.3-full-api` branch shipped as a **git bundle** (no push),
  cloned on the host; HEAD `1201ac8` (before this evidence + the test fix `71c320f`).
- **Python:** CPython **3.14.6**, installed via `uv python install 3.14` (the project's `>=3.14` floor).
- **Install:** `uv pip install -e ".[dev,async,observability,orjson]"` — all native deps built/resolved
  on x86_64.
- **Live stack:** `./local-stack.sh -o start` → Elasticsearch + Kibana **9.4.3** (single-node, trial
  license) via Docker. `vm.max_map_count=262144` set (Linux ES prerequisite).

## Native dependency check (x86_64)

All architecture-sensitive dependencies import and function:

| Dependency | Version | Note |
|---|---|---|
| aiohttp | 3.14.1 | async transport |
| orjson | 3.11.9 | Rust extension — `orjson.loads(orjson.dumps(...))` round-trip verified |
| grpcio | 1.81.1 | OTLP gRPC exporter (observability extra) |

## Unit suite

```
.venv/bin/python -m pytest tests/unit/
=> 3011 passed in 34.99s   (94% coverage)
```

- **5 more passing than the arm64/macOS run** (which reports `3006 passed, 5 skipped`): tests skipped
  on macOS run and pass on Linux x86_64.
- The `orjson` serialization path is exercised on this host (serializer coverage 65% → 82%), because
  the `orjson` extra was installed.

## Live integration suite (real ES + Kibana 9.4.3 on x86_64)

A representative core subset (11 files across platform, security, and the new Dashboards/
Visualizations APIs) was run against the live stack:

```
pytest tests/integration/{test_status,test_spaces,test_saved_objects,test_data_views,
  test_connectors,test_alerting,test_cases,test_lists,test_short_urls,
  test_visualizations,test_dashboards}_integration.py
=> 129 passed, 1 failed in 268s (0:04:28)
```

### The one failure — not architecture-related, now fixed

`tests/integration/test_lists_integration.py::TestListsIndexStatus::test_get_index_status` failed
with `NotFoundError: [404] data stream .lists-default and data stream .items-default does not exist`.

Root cause: the test assumed the shared value-list data streams already existed, but on a **fresh**
stack they don't until `create_index()` runs, so the result depended on test order. This is a
test-isolation issue that would fail identically on arm64 against a fresh stack — **not** a
cross-architecture defect (the client code is pure Python; the arch-sensitive native deps all
passed).

**Fixed** in commit `71c320f`: a class-scoped autouse fixture ensures the index exists before the
status assertions (`create_index` is idempotent on 9.4.3). Verified by deleting the index to
reproduce the 404, then passing all three status tests and the full `test_lists_integration.py`
(11 passed).

## Teardown

Per `secrets-and-teardown-discipline`: `./local-stack.sh -o destroy` (containers + volumes removed),
then the cloned repo, the git bundle, and the copied dev `.env`/`.env.local` were deleted. Verified
zero — no `kibana`/`es` containers or volumes, no repo remaining (only the ES/Kibana Docker images
left cached, which hold no state).

## Verdict

**The project works on Intel/x86_64.** Native deps build and pass, the full unit suite passes (with
broader coverage than macOS), and the live integration subset passes against a real 9.4.3 stack. The
sole failure was a pre-existing fresh-stack test-isolation quirk, now fixed.
