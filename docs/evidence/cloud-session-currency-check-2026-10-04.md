# Evidence — currency check and full live loop from a cloud session

**Date:** 2026-10-04
**Machine:** Claude Code cloud session VM, x86_64, 4 vCPUs, 15 GiB RAM, Docker 29.6.2.
**Commits under test:** `6379224` (`main`, release 0.6.0) for both suite runs; `1f655db` for the
`cloud-session-start.sh` fix found along the way.

## Why

Two questions: is there a Kibana release the supported set should move to, and can a cloud
session carry a version move end to end — detect, provision, test, fix, commit, push — without a
maintainer's laptop.

## 1. Currency: nothing to move to

```text
$ python3 scripts/checks/supported-versions.py --latest
Kibana support currency (source: kibana/_compat.py)
  CURRENT  9.5: 9.5.4 is the latest patch
  CURRENT  9.4: 9.4.7 is the latest patch
```

Cross-checked against the raw tag list of `docker.elastic.co/v2/kibana/kibana/tags/list`
(48,313 tags), filtered to 9.4 and up:

| Line | Newest release tag | Newer tags present |
| :--- | :--- | :--- |
| 9.5 | `9.5.4` | `9.5.5-SNAPSHOT` builds only |
| 9.4 | `9.4.7` | `9.4.8-SNAPSHOT` builds only |
| 9.6 | — | `9.6.0-SNAPSHOT` builds only |
| 10.x | — | none |

Snapshots are not releases, so the pins stay. 9.4.8, 9.5.5 and 9.6.0 are in flight.

## 2. A finding: the session started with no Docker daemon

`cloud-session-start.sh` had not run: the session's working directory was the parent of the
clone, so the project's `SessionStart` hook was never loaded. Run by hand, it then failed too:

```text
[cloud-session-start] dockerd did not come up; see /var/log/kibana-py-dockerd.log
failed to start daemon, ensure docker is not running or delete /var/run/docker.pid:
process with PID 567 is still running
```

`/var/run/docker.pid` (567) came from the setup run that built the snapshot. At hook time some
unrelated early-boot process held that PID. Fixed in `1f655db`: with no `dockerd` running, the
hook removes the pidfile before launching one.

Replayed with a planted decoy: a live `sleep` process's PID written to the pidfile.

```text
--- OLD hook (HEAD~1):
[cloud-session-start] dockerd did not come up; see /var/log/kibana-py-dockerd.log
failed to start daemon, ensure docker is not running or delete /var/run/docker.pid: process with PID 13196 is still running
--- NEW hook (HEAD):
[cloud-session-start] started dockerd (server 29.6.2)
```

## 3. Both pins, live

Images came from the snapshot (`/var/log/kibana-py-cloud-setup.log`: six images cached in 116s).
Install: `pip install -e ".[dev,all,probe]"` into a fresh `.venv`; `--ignore-installed` was not
needed on this image. API key minted per the cloud-environment page.

```bash
ES_LOCAL_VERSION=<pin> ./scripts/ci-stack-up.sh
python -m pytest tests/integration/ -q -p no:randomly -p no:cacheprovider \
  -o addopts="" -m "not flaky" --timeout=180 --timeout-method=signal -ra
```

| Pin | Stack up | Collected | Passed | Failed | Errors | Skipped | Wall |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 9.5.4 | 189s | 768 | 750 | 0 | 0 | 18 | 22m45s |
| 9.4.7 | 171s | 768 | 749 | 0 | 0 | 19 | 21m57s |

Against the 2026-09-20 laptop runs E and F in `multi-version-9.4.7-9.5.4.md` (753/15 and
752/16), each pin has exactly three more skips, and they are the same three on both:

```text
test_security_ai_assistant_integration.py:342  ELSER-2 inference unavailable ... SSLHandshakeException (certificate_unknown)
test_security_ai_assistant_integration.py:398  same
test_streams_integration.py:246                same
```

That is Elasticsearch's JVM rejecting the session's egress CA, the gap
`elastic-start-local/docker-compose.proxy-ca.yml` documents and deliberately leaves open (the
overlay gives Kibana the CA, not Elasticsearch). The tests skip cleanly instead of failing, so
this is an environment limit and not a client regression.

The only per-pin difference is
`TestRemovedCapabilities::test_the_error_names_where_the_capability_does_exist`, which passed
on 9.5.4 and was skipped on 9.4.7 (`the endpoint is routed on 9.4; nothing to refuse`). The
earlier evidence records the same difference.

Headroom with the 9.5.4 stack running the suite: 5.1 GiB RAM used of 15, 20 GiB disk free.

## 4. Fast gates on this tree

| Gate | Result |
| :--- | :--- |
| `make versions` | GO — every version statement agrees with the source |
| unit tests + coverage | 3531 passed, 1 skipped, 94.52% (floor 90%) |
| pre-commit on changed files | all passed |

## Verdict

| Claim | Status |
| :--- | :--- |
| A session can detect a new Kibana release | **PASS**: registry check plus raw tag list |
| A session can provision both pins and run the full suite | **PASS**: 0 failed, 0 errors on each |
| A session can fix, commit and push to the repo | **PASS**: `1f655db` pushed |
| Results match the laptop baseline | **PASS with a stated gap**: 3 ELSER tests skip on the cloud VM (proxy CA) |
| The `SessionStart` hook starts Docker unaided | **FAIL before `1f655db`**, pass after. It still needs the session to start inside the repo |
