# Evidence — moving the pins to Kibana 9.4.9 and 9.5.6

**Date:** 2026-11-08
**Machine:** Claude Code cloud session VM (weekly version-watch routine), x86_64, Docker from the
session image, the repo's `.venv` from `make setup`.
**Commits under test:** the pin commit and the test commit on `claude/awesome-wright-le1rst`.

## Why

```text
$ python3 scripts/checks/supported-versions.py --latest
Kibana support currency (source: kibana/_compat.py)
  DRIFT    9.5: pinned 9.5.5, latest released 9.5.6
  DRIFT    9.4: pinned 9.4.8, latest released 9.4.9
```

The set of lines does not change, so this is the patch procedure in
`docs/source/development/version-support.md`: no support decision, but a live run on both pins.
In flight, as `-SNAPSHOT` tags only: 9.6.0 and 9.7.0. No 10.x.

## Method

```bash
ES_LOCAL_VERSION=<pin> ./scripts/ci-stack-up.sh
export ES_LOCAL_API_KEY=...   # minted per cloud-environment.md
python -m pytest tests/integration/ -q -p no:randomly -p no:cacheprovider \
  -o addopts="" -m "not flaky" --timeout=180 --timeout-method=signal -ra
```

## Result

| Pin | Stack up | Passed | Failed | Skipped | Wall |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 9.5.6 (first run, before the test change) | 106s | 748 | 2 | 18 | 22m06s |
| 9.5.6 (the two failing classes, after) | — | 10 | 0 | 0 | <1s |
| 9.4.9 (full suite, with the test change) | 104s | 749 | 0 | 19 | 22m25s |

The 9.5.6 full suite was not re-run end to end after the test change; only the two classes that
held the failures were (`TestFleetEpmSemanticErrors`, `TestOsqueryLiveQueries`, 10 passed).

Skips are the expected set: the three ELSER tests (the session proxy CA is rejected by
Elasticsearch), OTLP/LLM-backend tests with nothing configured, and on 9.4.9
`test_the_error_names_where_the_capability_does_exist`.

## Two failures on 9.5.6: server answers changed

Both are server behavior changes the client passes through correctly, so no `_compat.py`
mechanism applies; the tests now accept the old and new answer.

1. `test_authorize_transforms_package_not_installed`: 404 "not found" became
   `403 Cannot reauthorize transforms from a non-registry package ...`. The client raises
   `AuthorizationException` for the 403, as designed.
2. `test_get_live_query_unknown_id_server_behavior`: 500 "no elements in sequence" became
   `404 Action not found`. The `get_live_query` docstrings (sync and async) now name both.

Which answer 9.4.9 gives for these two was not separately recorded; the broadened assertions
passed there in the full run.
