# Evidence — moving the pins to Kibana 9.4.7 and 9.5.4

**Date:** 2026-09-20
**Machine:** the maintainer's aarch64 macOS laptop. The 9.4.5/9.5.2 evidence was taken on
the x86_64 cloud session VM, so this run is not a re-measurement of that one on the same
hardware — it is the same suite, one machine over.
**Commits under test:** `3256ffc` (the pins and their mirrors), `b81ad54` (documentation),
`07a0588` (the suite and docstring changes this run forced).

## Why

`scripts/checks/supported-versions.py --latest` reported both pins stale against the
Elastic registry: 9.5.2 → 9.5.4 and 9.4.5 → 9.4.7. The policy is the two most recent minor
lines at the latest patch of each, so the pins move. A patch move is steps 1, 5, 6, 7 and 8
of the procedure in `docs/source/development/version-support.md` — no support decision,
because the *set of lines* does not change, but a live run on both pins, because a patch is
not obviously safe.

It was not. Four Fleet routes answer differently on the new patches than on the old ones,
identically on both lines.

## Machine

| | |
|---|---|
| Role | maintainer's laptop, macOS 27.0 (build 26A428), `Darwin 27.0.0 arm64` |
| CPU / RAM available to Docker | 18 CPUs / 11.7 GiB |
| Docker | Engine 29.8.0 |
| Python | CPython 3.13.7, the repo's `.venv` (editable install) |
| Stack | `./scripts/ci-stack-up.sh`, one version at a time, volumes destroyed between |

## Method

```bash
# per version
docker compose -f docker-compose.yml -f docker-compose.apm.yml down --volumes --remove-orphans
ES_LOCAL_VERSION=<pin> ./scripts/ci-stack-up.sh

python3 -m pytest tests/integration/ \
  -o addopts="" -p no:randomly -p no:cacheprovider \
  --timeout=180 --timeout-method=signal -q -ra --junitxml=<report>
```

with `KIBANA_URL=http://localhost:5601`, `KIBANA_USERNAME=elastic`,
`KIBANA_PASSWORD=kibana-py-es-dev`, and an `ES_LOCAL_API_KEY` minted per run, exactly as
`ci-stack-up.sh` does in CI — which matters more than usual here, because one of the four
findings is about what an API key is allowed to do.

## 1. The pins were stale, and no new line exists — from the registry

```
$ python3 scripts/checks/supported-versions.py --latest
Kibana support currency (source: kibana/_compat.py)
  DRIFT    9.5: pinned 9.5.2, latest released 9.5.4
  DRIFT    9.4: pinned 9.4.5, latest released 9.4.7
```

Confirmed independently against the registry's tag list, which also settles the question
the `--latest` check answers by silence:

```
9.0 latest patch: 9.0.8      9.3 latest patch: 9.3.8
9.1 latest patch: 9.1.10     9.4 latest patch: 9.4.7
9.2 latest patch: 9.2.8      9.5 latest patch: 9.5.4
highest line overall: 9.5
```

No `9.6.x` tag exists, so the two most recent minor lines are still 9.5 and 9.4: the
supported *set* is unchanged and the oldest-line decision is not reopened.

## 2. The first runs — four failures, the same four on both pins

Full suite, at `3256ffc`/`b81ad54`, before any suite change:

| Run | Version | Result | Wall |
|---|---|---|---|
| A | 9.5.4 | **4 failed**, 747 passed, 15 skipped | 21m39s |
| B | 9.4.7 | **4 failed**, 746 passed, 16 skipped | 21m24s |

The same four tests, on both lines:

| Test | Server said |
|---|---|
| `test_fleet_agents…::test_get_uploads_for_unknown_agent` | `404 Agent <id> not found` |
| `test_fleet_enrollment…::test_rotate_key_pair_acknowledged` | `403 Rotating the key pair requires superuser privileges.` |
| `test_fleet_epm…::test_install_package_by_upload` | `400 Cannot upload a package whose name already exists in the package registry or as a bundled package: tcp` |
| `test_fleet_policies…::test_delete_agentless_policy_unknown_id_is_idempotent` | `404` (worded differently on each line) |

None carries the `flaky` marker, so the release gate — which runs `-m "not flaky"` — would
have failed on all four.

## 3. Attribution — the same four tests, four server versions, one machine, one day

A failure on a new pin is not by itself a finding about the new pin: this machine is not
the machine the previous evidence was taken on, and one of the four failures depends on
what the package registry happens to serve today. So the same selection was run against
both old pins and both new ones, in the same isolated form, within twenty minutes:

| Test | 9.4.5 | 9.5.2 | 9.4.7 | 9.5.4 |
|---|---|---|---|---|
| unknown agent's uploads | pass | pass | **404** | **404** |
| rotate key pair (API key) | 500¹ | 500¹ | **403** | **403** |
| upload install of a registry archive | pass | pass | **400** | **400** |
| delete unknown agentless policy | pass | pass | **404** | **404** |

¹ The isolated 500 is a separate, pre-existing property of that test — section 4.

Three behaviours therefore changed **in lockstep on both lines**, between 9.4.5→9.4.7 and
9.5.2→9.5.4: backports, not a line divergence. The registry-contents hypothesis for the
upload failure is refuted by the same table: the old pins accepted the identical archive,
downloaded from the same registry, on the same afternoon.

## 4. The rotation finding: an authorization change, plus an order dependency it exposed

Two different things were tangled in that row, and they separate cleanly. Whole
`test_fleet_enrollment_integration.py` file, both auth modes, both 9.5 pins:

| | API key | basic auth (elastic) |
|---|---|---|
| **9.5.4** | 1 failed (`403 … requires superuser privileges`), 13 passed | **14 passed** |
| **9.5.2** | 14 passed | 14 passed |

So: the route now requires superuser, and the privileges an API key carries no longer
satisfy it. The client is not involved — it sends what it is told to send and surfaces the
server's 403 as `AuthorizationException`.

The `500 Failed to rotate key pair!` in section 3 is not version-related at all. It
reproduces on a **fresh 9.4.7 stack** when the test class runs alone, and disappears when
the whole file runs — the route needs Fleet to have been set up, which creating an agent
policy does, and an earlier test in the file happened to do it:

```
class alone, fresh stack:          1 failed (500), 1 passed, 1 skipped
whole file, same fresh stack:      14 passed, 1 skipped
class alone, after the fixture:    2 passed, 1 skipped
```

The test now requests the file's own `agent_policy` fixture for its side effect, so it
carries its own prerequisite instead of depending on collection order. That failure mode
predates this change; the pin move is what surfaced it.

## 5. The upload finding: the success path still exists, under a name the registry lacks

The new rejection is about the *name*, not about uploading. Probed directly on 9.5.4: the
`tcp` archive was downloaded from the registry, its top-level directory and its root
manifest's `name:` rewritten to `kbnpy<random>`, and the result uploaded.

```
UPLOAD OK 200 {'install_source': 'upload', 'name': 'kbnpy2f49d914'}
status: installed
```

The first attempt of that probe returned `429 Too many requests. Please wait 10s before
uploading again.` on a stack that had received no other upload, so the route is also
rate-limited on the new patches. The suite's upload helper retries a 429 and nothing else.

Both facts are now in the `install_package_by_upload` docstring, and the suite asserts both
sides: the renamed archive installs, the registry-named archive is refused.

## 6. What the client needed: no code change

Both supported lines answer identically on all four points, so there is nothing for the
compatibility layer to absorb — no normalizer, no `CAPABILITIES` row, no version branch.
`SUPPORTED_VERSIONS` moves, and that is the whole of the change under `kibana/`:

```
$ git diff 3256ffc..07a0588 --stat -- kibana/
 kibana/_async/client/fleet_agents.py     |  5 +++++
 kibana/_async/client/fleet_enrollment.py | 10 +++++++---
 kibana/_async/client/fleet_epm.py        | 11 ++++++++++-
 kibana/_async/client/fleet_policies.py   |  8 ++++++--
 kibana/_sync/client/fleet_agents.py      |  5 +++++
 kibana/_sync/client/fleet_enrollment.py  | 10 +++++++---
 kibana/_sync/client/fleet_epm.py         | 11 ++++++++++-
 kibana/_sync/client/fleet_policies.py    |  8 ++++++--
 8 files changed, 56 insertions(+), 12 deletions(-)
```

— docstrings only, in both trees, recording what each route now does and what it used to do.

This is a **fourth kind of divergence**, and worth naming next to the three the design doc
already classifies: *the same behaviour change, backported to every supported line at
once*. It needs no mechanism, because there is no disagreement between lines to reconcile.
What it needs is for the suite to stop asserting the old behaviour — the client's job here
was only to keep surfacing the server's own status codes as typed exceptions, which it did
without modification.

## 7. The certification runs

Same commit `07a0588`, same suite, one server version apart:

```
E (9.5.4): collected=768 passed=753 failed=0 error=0 skipped=15 wall=1305.2s exit=0
F (9.4.7): collected=768 passed=752 failed=0 error=0 skipped=16 wall=1299.4s exit=0
```

The two runs collect the **same 768 tests** and differ by **exactly one outcome**:

```
9.5.4 passed / 9.4.7 skipped
   test_version_compat_integration.TestRemovedCapabilities
   ::test_the_error_names_where_the_capability_does_exist
```

That is the deliberate skip — on 9.4 the endpoint is routed, so there is no refusal whose
message could be checked. It is the same single exception the 9.4.5/9.5.2 pair showed, which
is what "one contract across both lines" means when it is measured rather than asserted.

Against runs A and B, per version, the outcome diff is exactly the intended one:

```
failed -> passed   test_get_uploads_for_unknown_agent
failed -> passed   test_rotate_key_pair_acknowledged
failed -> passed   test_install_package_by_upload
failed -> passed   test_delete_agentless_policy_unknown_id_is_idempotent,
                   renamed to ..._unknown_id_raises_not_found
added (passed)     test_rotate_key_pair_refuses_api_key_authentication
added (passed)     test_install_package_by_upload_rejects_a_registry_name
```

Nothing went `passed -> failed`, `passed -> skipped`, or out of collection, on either line.

**The tree each run measured.** Run E started at `07a0588` with `dirty_paths=0`. Run F
reported `dirty_paths=7`: this evidence file, `README.md`, `CHANGELOG.md`,
`docs/source/development/version-support.md` and three `docs/source/api-reference/*.rst`
pages were being written while it ran. Nothing under `kibana/` or `tests/` differed from
`07a0588` during either run — those seven paths are the whole of the difference, and none of
them is imported by the suite.

## 8. Scorecard

| Claim | Verdict |
|---|---|
| 9.4.7 and 9.5.4 are the latest patch of their lines | **PASS** — registry tag list |
| No newer minor line exists | **PASS** — highest tag line is 9.5 |
| The four failures are properties of the new patches, not of this machine or this day | **PASS** — section 3, old pins measured alongside |
| The three semantic changes are identical on both lines | **PASS** — same status on 9.4.7 and 9.5.4 |
| The rotation change is an authorization change | **PASS** — section 4 auth matrix |
| The upload-install success path survives | **PASS** — section 5, renamed archive installs |
| The client needed no code change | **PASS** — `kibana/` diff is docstrings only |
| Both pins green after the suite change | **PASS** — runs E and F, 0 failed, 0 errors, exit 0 |

### What this does not establish

- **Exhaustive API equivalence.** 610 endpoints are exercised and four routes changed; a
  response field no assertion reads could still differ.
- **That the four changes arrived in these exact patches.** 9.4.6 and 9.5.3 were not
  measured — only that 9.4.5/9.5.2 behave one way and 9.4.7/9.5.4 the other.
- **Which upstream change caused them.** The Kibana 9.5.4 and 9.5.3 release notes do not
  mention any of the four; the behaviour is recorded from the server itself, not from them.
- **x86_64 behaviour.** This run is aarch64. The GitHub matrix and the cloud environment
  are where the x86_64 result comes from.
