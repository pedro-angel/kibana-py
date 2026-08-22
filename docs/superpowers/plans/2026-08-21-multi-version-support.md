# Multi-Version Kibana Support — Implementation Plan

**Date:** 2026-08-21
**Status:** Complete — every task done and verified; see the "Result" line on each.
**Phase:** 5 of 5 (TASKS). Consumes:
[SPECS](../specs/2026-08-21-multi-version-support-spec.md) and
[DESIGN](../specs/2026-08-21-multi-version-support-design.md).
**Branch:** `claude/kibana-multi-version-sdd-rx4a3a`
**Evidence:** [`docs/evidence/multi-version-9.4.5-9.5.2.md`](../../evidence/multi-version-9.4.5-9.5.2.md)

**Goal:** Kibana 9.4.5 and 9.5.2 are both supported, both release-gated, and the
supported set can move forward by procedure rather than by archaeology.

## Global constraints

- Every client change is made in **both** trees. `kibana/_sync/` and `kibana/_async/`
  are hand-maintained parallel implementations, not generated — a change to one that
  is not made to the other is a silent async-only bug.
- Additive only. No key the server sent may be removed, renamed, or overwritten; no
  call that worked on 9.4 may start failing.
- Conventional-Commit subjects with a provenance trailer (`commit-msg` hooks enforce
  both). Commits whose correctness rests on a live run carry `Evidence:`.
- The live server outranks the release notes. Every contract claim in this plan was
  measured against a running stack before it was written down.
- Never `git add -A`; stage the files each task names.

---

### Task 1 — Measure both lines live, before designing anything

**Files:** none (research).

- [x] Confirm the latest patch of each supported line from the container registry, not
      from memory. **Result:** 9.4.5 and 9.5.2; the repository was pinned two and one
      patch behind. No 9.6 line exists, so the supported lines stay 9.5 and 9.4.
- [x] Bring up 9.5.2 and probe every divergence the prior evidence claimed.
      **Result:** two of the three claims reproduced; one was refuted — see RESEARCH §3.
      A fourth, previously unrecorded, was found: `_preview` is removed as well as
      `_generate`.
- [x] Establish where the removed endpoints went, from the server's own route table
      rather than by guessing paths. **Result:** they did not move to another public
      path; significant-events generation became an internal surface in 9.5.

### Task 2 — The compatibility core

**Files:** create `kibana/_compat.py`; modify `kibana/exceptions.py`, `kibana/__init__.py`.

- [x] `SUPPORTED_VERSIONS`, `SUPPORT_DECISIONS`, `CAPABILITIES` — the declared set.
- [x] `parse_version`, `minor_line`, `is_supported`, `supported_lines`, `supported_pins`.
- [x] `capability_available` / `capability_lines`, failing **open** on an unknown or
      unsupported version.
- [x] `normalize_dashboards_search`, `normalize_significant_events` — additive, both
      directions, in place, non-`dict` bodies passed through untouched.
- [x] `ServerVersionCache` — the resolved-once holder.
- [x] `KibanaVersionError` carrying `capability`, `server_version`, `available_on` and an
      optional `hint`. A capability is a method **or** a request field, named the same way
      (`streams.upsert.queries`), so both go through one check.
- [x] Export `SUPPORTED_VERSIONS`, `is_supported`, `KibanaVersionError`.
      **Result:** `tests/unit/test_compat.py`, 62 tests, green.

### Task 3 — Server version on the client

**Files:** `kibana/_sync/client/_base.py`, `kibana/_async/client/_base.py`.

- [x] `server_version()` on both, lazily reading `/api/status`, caching in a
      `ServerVersionCache`.
- [x] `options()` shares the holder, matching the space cache's rule.
- [x] Errors from `/api/status` propagate to a caller who asked directly and are **not**
      cached, so a transient failure does not poison the client.

### Task 4 — The capability gate

**Files:** `kibana/_sync/client/utils.py`, `kibana/_async/client/utils.py`.

- [x] `_server_version_or_none()`, `_capability_available()` and `_require_capability()`
      on both `NamespaceClient`s. All three fail **open**: they refuse only where absence
      is proven, and proceed on an unreadable version, an unsupported server, or a
      capability nothing has measured.

### Task 5 — Apply the adapters at the endpoints

**Files:** `kibana/{_sync,_async}/client/dashboards.py`, `.../streams.py`.

- [x] `dashboards.get_all()` normalizes its response; docstring states both spellings.
- [x] `streams.get_significant_events()` normalizes its response; docstring likewise.
- [x] `streams.upsert()` gates the `queries` field on the server version — supplied on
      9.4 (which requires it), omitted on 9.5 (which rejects it), and an explicit
      `queries` against 9.5 raises with a hint rather than being dropped. **This task
      changed after Task 1's 9.4.5 measurement refuted the version-free approach it was
      written for**; SPECS R3 and DESIGN §1 were reconciled to match.
- [x] `streams.generate_significant_events()` and `preview_significant_events()` call
      the gate first; docstrings name the line boundary.

### Task 6 — The maintenance framework

**Files:** create `scripts/checks/supported-versions.py`,
`docs/source/development/version-support.md`; modify `Makefile`, `dod.config`,
`scripts/checks/definition-of-done.sh`, `docs/source/development/index.md`.

- [x] `--check` compares every mirror against the source and names each disagreement.
- [x] `--matrix` emits the pins as JSON, read with `ast` so no install is needed.
- [x] `--latest` asks the registry, and reports an unreachable registry as **UNKNOWN**
      rather than as agreement.
- [x] The decision check: a dated row per supported line, and the oldest line's verdict
      must read `kept`.
- [x] `make versions`, wired into `make check` and into `dod.config` as
      `versions_consistent`.
- [x] The version-support page: policy, procedure, criteria, decision record.

### Task 7 — Move the mirrors onto the new set

**Files:** `elastic-start-local/.env.example`, `scripts/cloud-setup.sh`,
`.github/workflows/integration-probe.yml`, `.github/workflows/release.yml`,
`docs/source/development/cloud-environment.md`, `README.md`, `docs/source/quickstart.md`,
`examples/README.md`.

- [x] Both workflow matrixes derive from the source via a `versions` job.
- [x] The release gate matrixes over the whole supported set — SPECS R12: the supported
      set and the release-gated set are now the same list by construction.
- [x] Every prose mirror updated; `make versions` GO.

### Task 8 — Prove it live on both pins

**Files:** create `tests/integration/test_version_compat_integration.py`,
`docs/evidence/multi-version-9.4.5-9.5.2.md`.

- [x] Live contract tests that pass unchanged on both pins, plus the two
      deliberately version-aware capability tests, neither of which skips.
- [x] Full integration suite against live 9.5.2 and live 9.4.5, before and after.
- [x] Evidence artifact pinning commands, versions, commit, and per-suite results.

### Task 9 — Certify

- [x] `make dod` → **10 GO, 2 NO-GO**, both NO-GOs properties of the sandbox rather than
      the repository: `unit_green` (the Firecracker kernel has no IPv6 and one unit test
      needs a real IPv6 listener, so it skips, and the gate rejects any skip in the unit
      suite) and `docs_strict` (Sphinx linkcheck cannot reach six hosts outside the egress
      allowlist, none on a page this branch touches). Both certify in CI. Recorded in the
      evidence file and on the cloud-environment page rather than marked `n/a`.
- [x] CHANGELOG entry.

### Task 10 — Repairs the certification run itself demanded

Not planned. Each was found by running a gate rather than by reading code, and each is a
defect in the verification machinery, so each got its own commit.

- [x] **The two stack bring-up paths disagreed.** `ci-stack-up.sh` applied the proxy-CA
      overlay; `local-stack.sh` — which `make test-integration` and therefore the DoD gate
      use — did not. The same suite passed under one and failed under the other on the same
      commit and server. The decision now lives in `scripts/proxy-ca.sh`, sourced by both.
- [x] **The data-view fixture could not survive an interrupted run.** A unique id but a
      fixed name, and Kibana rejects duplicate data views by name, so one leftover failed
      four tests on a healthy stack.
- [x] **The telemetry-overhead benchmark was a coin flip.** A ratio of means over a
      network-dominated measurement: 1.04x, 1.59x, 0.97x on identical code. Medians plus an
      absolute floor.
- [x] **An IPv6 capability guard started one line too late**, so a host with no IPv6 failed
      where the author had intended it to skip.
