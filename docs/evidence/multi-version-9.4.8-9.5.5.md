# Evidence — moving the pins to Kibana 9.4.8 and 9.5.5

**Date:** 2026-10-27
**Machine:** Claude Code cloud session VM (weekly version-watch routine), x86_64, 15 GiB RAM,
Docker from the session image, the repo's `.venv` from `make setup`.
**Commits under test:** the pin commit on `claude/awesome-wright-ayyvdu` plus the Fleet EPM
test and docstring change described below.

## Why

```text
$ python3 scripts/checks/supported-versions.py --latest
Kibana support currency (source: kibana/_compat.py)
  DRIFT    9.5: pinned 9.5.4, latest released 9.5.5
  DRIFT    9.4: pinned 9.4.7, latest released 9.4.8
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

Volumes were destroyed between the two pins.

## Result

| Pin | Stack up | Passed | Failed | Skipped | Wall |
| :--- | ---: | ---: | ---: | ---: | ---: |
| 9.5.5 | 127s | 749 | 1 | 18 | 23m00s |
| 9.4.8 | 121s | 748 | 1 | 19 | 22m13s |

Headroom sampled once the 9.4.8 run had finished, stack still up: 6.2 GiB RAM used of 15.

Skips are the expected set: the three ELSER tests (the session proxy CA is rejected by
Elasticsearch), OTLP/LLM-backend tests with nothing configured, and on 9.4.8
`test_the_error_names_where_the_capability_does_exist`.

## The one failure: a Fleet error message changed, on both lines

`TestFleetEpmSemanticErrors::test_delete_datastream_assets_unknown_policy` failed identically on
both pins. The status is still 404; the message changed:

```text
Expected regex: 'Package policy with id kbnpy-bogus not found'
Actual message: '[404] Saved object [fleet-agent-policies/kbnpy-bogus] not found'
```

Classification: a server wording change, not a client defect. The client raises `NotFoundError`
as before and passes the message through, so no `_compat.py` mechanism applies. The test now
accepts either wording and the two `delete_datastream_assets` docstrings (sync and async) name
both. After the change the test passed against the running 9.4.8 stack. 9.5.5 was not re-run
after the change; its failing message was the same one observed on 9.4.8.

## Gates

`make versions`: GO. `make dod`: **NO-GO**, two criteria, both environmental:

| Criterion | Result | Cause |
| :--- | :--- | :--- |
| `unit_green` | NO-GO | 3531 passed, 1 skipped in a no-skip suite: `test_observability.py:1471`, IPv6 unavailable on the session VM |
| `matrix_green` | NO-GO | nox sessions 3.11, 3.12, 3.13 passed; 3.14 failed, interpreter not installed on the VM |
| `integration_green` | GO | 749 passed, 19 skipped (9.4.8 stack, after the test fix) |
| every other criterion | GO | |

Neither failure touches the version move; both need a host with IPv6 and Python 3.14.
