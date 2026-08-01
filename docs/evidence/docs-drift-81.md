# Evidence — docs drift found by the 2026-07-31 release review (#81)

**Date:** 2026-08-01
**Change under test:** six documentation-drift fixes filed as issue #81, re-verified against
`main` at the current HEAD (9 merged fix PRs — #85 through #95 (non-contiguous: #91/#92 are
unrelated open issues, not PRs in this window) — closing issues #68 and #70 through #80, all
merged since #81 was filed on 2026-07-31, so every item was re-checked against the tree as it
exists now, not as it existed when the issue was opened).
**Base commit:** `b2bf7e9` (branch `fix/docs-drift-81`).

## Method

Per the campaign's currency-and-audit-before-trust discipline, a checklist filed against an
older tree is a hypothesis, not a fact, at the point of fixing it. For each of the six items:
1. Re-read the *current* source of truth (the code, `release.yml`, `pyproject.toml`) at HEAD.
2. Re-read the *current* doc text the issue complained about.
3. Only then decide: still valid as filed / already fixed by an intervening PR / valid but the
   correct fix has shifted.

All six items were **still valid at HEAD** — none of the 9 intervening fix PRs (#85–#95,
closing issues #68 and #70–#80) touched release process docs, the observability docs, the
installation docs, the `flaky` marker, or the root changelog's policy language. Dispositions
below.

## Dispositions

### 1. `docs/source/changelog.md` missing 0.4.1 + 0.4.2

**Still valid.** Confirmed the file topped out at `## [0.4.0]` while the root `CHANGELOG.md`
already had `[0.4.2]` (2026-07-15) and `[0.4.1]` (2026-07-12) sections.

**Fix:** added condensed `(v0.4.2)=` / `(v0.4.1)=` sections mirroring the root CHANGELOG's
`### Fixed` bullets (TimelineClient space validation for 0.4.2; transport-error translation +
space-existence-check hardening for 0.4.1), each linking back to the root CHANGELOG for full
detail — matching this file's existing convention for patch releases (see the `[0.3.1]`
section, which already does this). Updated the reference-link footer: added `[0.4.2]` and
`[0.4.1]` tag links, rebased `[Unreleased]` onto `v0.4.2...HEAD`.

Also added the "add this file to the release checklist" half of the ask: `release-process.md`'s
pre-release checklist now has its own bullet for `docs/source/changelog.md`, and Step 2 ("Update
the changelog") now explicitly says to mirror an entry into it, since it ships with the built
docs (RTD, PyPI project links) and is not generated from the root file.

**Ruling on "mirror" (MINOR, accepted):** the issue's literal text says "mirror the root
CHANGELOG," which read strictly could mean a verbatim copy of the (very long) root entries.
This fix instead uses the same **condensed-with-link** style `docs/source/changelog.md` already
uses for every prior patch release — see the existing `[0.3.1]` section, which summarizes and
then says "See the root CHANGELOG for full detail" rather than reproducing it. That precedent
stays the convention here too: the 0.4.1/0.4.2 sections are condensed summaries with a link
back, not verbatim copies. Dispositioned explicitly rather than left as a silent judgment call.

### 2. `release-process.md` contradicts `release.yml` (missing 5th `integration` job)

**Still valid.** Read `release.yml` fresh at HEAD (not from memory) — it has **5** jobs:
`validate-release` → `build` + `integration` (parallel) → `publish-github-release` (needs
`[build, integration]`) → `publish-pypi` (needs `[build, publish-github-release]`). The
`integration` job name is literally `"Integration tests (release gate)"`, provisions a live
ES+Kibana+APM stack via `scripts/ci-stack-up.sh`, and runs
`make test-integration-ci PYTEST=pytest` (i.e. `pytest -m "not flaky"`) — a real release gate,
not a rumor. `release-process.md`'s mermaid diagram (4 nodes: validate/build/ghrel/pypi) and
jobs table (4 rows) had no `integration` node/row at all, and its pre-release checklist stated
*"CI does not run \[`make test-integration`\] (needs a Docker Elastic Stack)"* — false; it's
been running as `integration` in `release.yml` since before this issue was filed.
`PUBLISHING_GUIDE.md` (its "Step 8: Monitor the workflow" section, item 3 "Integration gate")
already documented the 5-job graph correctly, confirming the two release docs contradicted each
other exactly as the issue described.

**Fix:** `release-process.md`'s intro paragraph, mermaid diagram, and jobs table now show the
real 5-job graph (added the `integration` node/row, parallel to `build`, feeding
`publish-github-release`). The pre-release checklist bullet was reworded from a false claim to
an accurate one: local `make test-integration` is recommended for fast feedback, and the tagged
release's `integration` job is the actual required gate. No other content in `release-process.md`
needed to change — `release.yml` was not modified by intervening PRs (per the task framing, PR
#82's release.yml work is queued later and had not landed at this HEAD; confirmed by reading the
file fresh rather than assuming).

### 3. `observability.md` documents nonexistent `validate_apm_connection`

**Still valid.** `kibana/observability/_validation.py:103` defines
`validate_apm_server_availability(endpoint: str, headers: dict[str, str] | None = None,
protocol: str = "grpc") -> bool`; `kibana/observability/__init__.py` re-exports it. No
`validate_apm_connection` name exists anywhere in `kibana/`. `observability.md` (the "APM Server
Connectivity Validation" section) imported and called `validate_apm_connection` with no
`protocol` argument.

**Fix:** both the `import` line and the call site now use `validate_apm_server_availability`,
and the example now passes `protocol="http/protobuf"` (with a comment noting `"grpc"` is the
default) to demonstrate the parameter the issue flagged as undocumented.

### 4. `installation.md` + `observability.md` undercount the `observability` extra (3 vs 5)

**Still valid.** `pyproject.toml`'s `[project.optional-dependencies].observability` lists
**5** packages: `opentelemetry-api`, `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`,
`opentelemetry-exporter-otlp-proto-http`, `opentelemetry-instrumentation`. Both docs pages
listed only the first 3, omitting the HTTP exporter and the instrumentation package — the same
gap the issue's second half (`protocol="http/protobuf"` documented while the extra that ships
its exporter goes unmentioned) pointed at.

**Fix:** both pages' "This installs:" bullet lists now enumerate all 5 packages.

**Note:** `docs/source/changelog.md`'s `[0.1.0]` historical section also lists 3 observability
packages (`### Optional Dependencies`) — left untouched. That section is a dated historical
record of what 0.1.0 actually shipped (before the HTTP exporter and instrumentation package
existed in the extra), not a current claim; editing it would misrepresent history rather than
fix drift.

### 5. `pyproject.toml` `flaky` marker implies an active quarantine, cites closed #53

**Still valid.** `gh issue view 53` confirms `state: CLOSED`. `grep -r "pytest.mark.flaky"
tests/` returns zero hits — the quarantine set is genuinely empty at HEAD, not just closed on
GitHub while still in use.

**Fix:** reworded the marker's help text from "...NOT auto-retried. See #53." to "...NOT
auto-retried. Quarantine is currently empty; last used for #53 (closed)." — states the current
(empty) state up front and keeps the provenance pointer to #53 for context, per the issue's
suggested wording.

### 6. Root `CHANGELOG.md`: codify the CI/tooling changelog policy

**Still valid** (this is a "decide and document" item, not a factual-drift item — nothing to
"re-verify still exists," but the underlying practice was verified against real commits before
being written down, per the docs-as-deliverable rule against aspirational documentation).
Evidence for the practice actually followed, not asserted from memory:

- **Dev-facing tooling change, logged despite touching no shipped code:** the `## [Unreleased]`
  section's `make audit` self-heal entry (issue **#80**, commit `f9066e3`) ships zero changes to
  `kibana/` but changes what a contributor's local `make audit`/`make dod` run does — it has a
  full CHANGELOG entry.
- **Pure CI-only plumbing, not logged:** commit `e2e072a` ("ci: share the pip+setuptools upgrade
  between `make setup` and CI", PR #67) touches only `.github/workflows/test.yml` and adds
  `scripts/upgrade-base-build-tools.sh` — `git show --stat e2e072a` confirms no `kibana/` path in
  the diff. `grep -c "^- \*\*.*[Ss]hare the pip" CHANGELOG.md` returns `0`: this commit has no
  standalone bullet of its own (it's only mentioned in passing, as context, inside the #80
  entry that builds on it).

This confirms the line the issue asked to codify: user-facing changes and dev-facing tooling
behavior changes (things a contributor actually runs) get an entry; plumbing only CI touches
does not.

**Fix:** added a one-line pointer comment under `CHANGELOG.md`'s Keep-a-Changelog preamble
("User-facing and dev-facing tooling changes get an entry; CI-only plumbing does not — see
CONTRIBUTING.md § Changelog Policy") and a full `### Changelog Policy` subsection in
`CONTRIBUTING.md` (placed after the existing Pull Request Checklist, which already had a terse
"CHANGELOG.md is updated with user-facing changes" bullet that this expands on) stating the rule
and citing the same two real commits as examples.

## Verification script (gate: every claimed name/command/count greps true against HEAD)

Script: `scripts/../` *(kept out of the repo — this is a one-off audit script, run from the
scratchpad; reproducible by pasting the block below into a shell at the repo root)*. Full output
captured verbatim below, run against this branch's HEAD after all edits:

```
== Item 1: docs/source/changelog.md has 0.4.1 + 0.4.2, mirroring root CHANGELOG ==
PASS: docs/source/changelog.md has a [0.4.1] heading
PASS: docs/source/changelog.md has a [0.4.2] heading
PASS: root CHANGELOG.md has the matching [0.4.1] heading (same date)
PASS: root CHANGELOG.md has the matching [0.4.2] heading (same date)
PASS: docs/source/changelog.md [Unreleased] compare link rebased on v0.4.2
PASS: docs/source/changelog.md has a [0.4.2] release-tag link
PASS: docs/source/changelog.md has a [0.4.1] release-tag link

== Item 2: release-process.md matches the actual release.yml job graph ==
PASS: release.yml declares an 'integration' job
PASS: release.yml integration job name is 'Integration tests (release gate)'
PASS: release.yml publish-github-release needs: [build, integration]
PASS: release.yml publish-pypi needs: [build, publish-github-release]
PASS: release-process.md mermaid diagram now shows the integration job
PASS: release-process.md jobs table now has an integration row
PASS: release-process.md no longer claims CI does not run integration tests
PASS: release-process.md checklist now names the CI integration gate
PASS: PUBLISHING_GUIDE.md documents the integration gate (already correct, unedited)
PASS: release-process.md now tells the release to also update docs/source/changelog.md

== Item 3: observability.md references the real validate_apm_server_availability name ==
PASS: kibana/observability exports validate_apm_server_availability
PASS: validate_apm_server_availability takes a protocol param
PASS: observability.md no longer references the nonexistent validate_apm_connection
PASS: observability.md now imports validate_apm_server_availability
PASS: kibana/observability/__init__.py actually re-exports validate_apm_server_availability
PASS: no remaining validate_apm_connection reference anywhere in docs/

== Item 4: observability extra package count/list matches pyproject.toml (5 packages) ==
pyproject.toml [observability] package count: 5
PASS: pyproject.toml observability extra has exactly 5 packages
PASS: installation.md documents opentelemetry-api
PASS: observability.md documents opentelemetry-api
PASS: installation.md documents opentelemetry-sdk
PASS: observability.md documents opentelemetry-sdk
PASS: installation.md documents opentelemetry-exporter-otlp-proto-grpc
PASS: observability.md documents opentelemetry-exporter-otlp-proto-grpc
PASS: installation.md documents opentelemetry-exporter-otlp-proto-http
PASS: observability.md documents opentelemetry-exporter-otlp-proto-http
PASS: installation.md documents opentelemetry-instrumentation
PASS: observability.md documents opentelemetry-instrumentation
PASS: installation.md lists 5 bullet points under the observability 'This installs' block
PASS: observability.md lists 5 bullet points under its 'This installs' block

== Item 5: pyproject.toml flaky marker no longer implies an active quarantine ==
PASS: flaky marker text says the quarantine is currently empty
PASS: flaky marker text still references #53 as closed, for provenance
PASS: no test in the tree currently carries @pytest.mark.flaky (quarantine really is empty)
PASS: issue #53 is in fact closed on GitHub

== Item 6: root CHANGELOG.md states the CI/tooling changelog policy ==
PASS: CHANGELOG.md points to the CONTRIBUTING.md changelog policy
PASS: CONTRIBUTING.md has a Changelog Policy section
PASS: policy cites the #80 make-audit fix as a logged dev-tooling example
PASS: cited #80 entry actually exists in CHANGELOG.md (Unreleased)
PASS: the cited pure-CI example (e2e072a, PR #67 title) has no standalone CHANGELOG.md bullet of its own
PASS: e2e072a is a real, merged, CI-only commit (not a hypothetical example)

ALL CHECKS PASSED
```

Exit status: `0`. **46 checks, all PASS, zero FAIL** — 36 direct `check` invocations in the
script plus 10 generated by its Item-4 per-package loop (2 checks × 5 packages), matching the
46 `PASS:` lines embedded above (`grep -c '^PASS:' docs/evidence/docs-drift-81.md` on this file
returns 46; an earlier draft of this report claimed 54, which did not reconcile against either
the script's `check` call sites or the embedded output — corrected here).

## Docs build gate (`make docs`)

```
$ make docs
.venv/bin/sphinx-build -W --keep-going -b html docs/source docs/build/html
... (full HTML build, all pages) ...
build succeeded.
.venv/bin/sphinx-build -b linkcheck docs/source docs/build/linkcheck
... (all external links ok/ignored/redirect; zero broken) ...
.venv/bin/pre-commit run check-diagrams-rendered --hook-stage manual --all-files
every mermaid fence rendered in the built docs (post-docs-build; run at CI/manual stage).......................Passed
```

Exit status: `0`. `-W` turns every Sphinx warning into a build failure, so the clean exit
confirms no broken MyST syntax, cross-reference, or heading-anchor markup in the touched pages.
The new `integration["<b>integration</b>..."]` mermaid node in `release-process.md` was
confirmed rendered (not just parsed) by the `check-diagrams-rendered` hook, which inspects the
built HTML for one rendered node per fence.

## Scope & caveats

- **No code changes.** Every edit in this fix is to a `.md` file, `pyproject.toml`'s marker
  *text* (a docstring-like config comment, not test-selection logic), `CHANGELOG.md`, or
  `CONTRIBUTING.md`. Nothing under `kibana/` changed.
- **release.yml itself was not modified.** Per the task framing, this fix describes the release
  workflow as it actually is at this HEAD; it does not change the workflow.
- **Item 6 is a policy decision, recorded as asked** ("decide and state the changelog policy"),
  not a factual bug fix — its "evidence" is that the stated policy matches observed practice on
  two real commits, not a test assertion.
