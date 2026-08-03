# Research brief — gate repair, coverage currency, #102, and the 0.5.0 cut

**Date:** 2026-08-03
**Status:** research (exploration, not a decision — decisions become specs/ADRs)
**Informs:** the DoD `vocabulary_conformant` repair, whether the release gains an
`### Added` section, the shape of the #102 fix, and the release checklist.

Every load-bearing claim below was checked against the live source (command run and
observed), not recalled. Source tier is noted where it matters.

---

## 1. The de-vendoring commit breaks three consumers, not one

`1a964a9` ("chore: de-vendor methodology — user-level pinned tier serves it now")
deleted `skills/`, `AGENTS.md`, and `CLAUDE.md` from the repo. Three things still
point at the deleted tree:

| Consumer | Reference | Consequence |
|---|---|---|
| DoD gate | `scripts/checks/definition-of-done.sh:93` | `vocabulary_conformant` NO-GO |
| CI | `.github/workflows/checks.yml:28` | `checks` job fails on push |
| Weekly bot | `.github/workflows/methodology-sync.yml:26-28` | re-vendors `skills/`, `AGENTS.md`, `CLAUDE.md` — undoes the de-vendoring |

Observed, not inferred:

```
$ skills/dev-environment-facade/vocabulary-conformance.sh; echo "exit=$?"
(eval):1: no such file or directory: skills/dev-environment-facade/vocabulary-conformance.sh
exit=127
```

**The commit is not pushed.** `origin/main` is at `4887c8a`; `1a964a9` is local-only.
CI is therefore still green *because the breakage has not reached the remote yet* —
it is a latent break, not an active one. The last GitHub `checks` run (30712047698,
2026-08-01) succeeded against `4887c8a`.

**The 2026-08-02 `make dod` GO verdict was recorded at `4887c8a` and does not
describe `HEAD`.**

### Where the checker lives now

`~/projs/agent-methodology/skills/dev-environment-facade/{vocabulary-conformance.sh,vocabulary.txt}`
— a developer-machine path. Not present on a GitHub runner, not present in a fresh
clone.

### What the checker actually requires (probed)

The script resolves its inputs in two different ways, which is the crux of the design:

- It `cd`s to the repo root itself (`cd "$(git rev-parse --show-toplevel)"`), so the
  Makefile it inspects is always the consuming repo's.
- It takes the manifest as `$1`, defaulting to the vendored path:
  `manifest="${1:-skills/dev-environment-facade/vocabulary.txt}"`.

So invoking it by absolute path **without** an argument fails — it still looks for a
repo-relative manifest:

```
$ ~/projs/agent-methodology/skills/dev-environment-facade/vocabulary-conformance.sh
FAIL: no vocabulary manifest at: skills/dev-environment-facade/vocabulary.txt
exit=2
```

Passing both paths works, and the Makefile itself is conformant:

```
$ M=~/projs/agent-methodology/skills/dev-environment-facade
$ "$M/vocabulary-conformance.sh" "$M/vocabulary.txt"
Vocabulary conformance (…/vocabulary.txt)
  GO    universal: help / setup / test / check / clean / dod
  GO    family: stack-* / test-integration / test-benchmark / build / lint / fix /
        audit / sast / hooks / docs / clean-all
  GO    floor: test, lint, audit, sast, hooks, docs in check's expansion
VERDICT: CONFORMANT
exit=0
```

**Conclusion: nothing is wrong with the Makefile. Only the path to the checker is
broken.** The repair is a locate-the-checker problem, not a conformance problem.

### Constraint from upstream

The checker's own header states the intended distribution model (primary source, the
script's comment block):

> the canonical name list is its vocabulary.txt (beside this script here in the
> methodology repo; **vendored under `skills/` in consuming repos, which execute the
> vendored copy rather than forking it**)

That is in direct tension with the de-vendoring commit and with the standing rule
recorded in the methodology-distribution memory ("never re-vendor scripts into
kibana-py"). The repo's established answer for *gates* is the pre-commit pattern:
consume upstream remotely at a **pinned rev** (`git-controls-starter`), never
main-tracking, never a hand-synced copy. Any repair should be judged against that
precedent.

---

## 2. Both weekly bots have been dead since 2026-07-13

Not previously known. Every scheduled run of both bot workflows has failed for three
consecutive weeks, with the same annotation:

> GitHub Actions is not permitted to create or approve pull requests.

| Workflow | Last success | Failing runs since |
|---|---|---|
| methodology sync | 2026-07-10 (manual `workflow_dispatch`) | 07-13, 07-20, 07-27, 08-03 |
| pre-commit autoupdate | none in the retained window | 07-13, 07-20, 07-27, 08-03 |

Both fail at the same step (`peter-evans/create-pull-request`); the steps before it
succeed, so the sync and the autoupdate both *ran* and produced changes — they just
could not open the PR. This is a repository/organization setting (Settings → Actions
→ General → Workflow permissions → "Allow GitHub Actions to create and approve pull
requests"), not a workflow bug.

**Implications.** The memory claim that vendored methodology "is kept fresh by a
weekly bot PR" is false in practice — no bot PR has landed since 2026-07-10. Same for
the pre-commit rev bumps. Whatever is decided about the vocabulary checker, the
methodology-sync workflow is currently inert, so it is not *actively* re-vendoring;
it would resume doing so the moment the setting is enabled.

---

## 3. Kibana API coverage — re-verified, no change, no work

**Primary source:** GitHub API against `elastic/kibana`.

- Latest release: **v9.4.4**, published 2026-07-21.
- Tags matching `v9.5+` or `v10+`: **none**.

The client was verified at 607/607 operations against v9.4.4 on 2026-07-31, and
nothing has shipped since. The forward-looking namespaces (Links, Markdowns,
Tags/saved-objects-tagging, Fleet managed integrations) remain `main`-only and
unreleased.

**This work item resolves as re-verified-no-op.** No `### Added` section; the release
scope is unchanged.

---

## 4. Issue #102 — exact sites and the fix's shape

The unredacted response-body log lives in `_process_response`, in both trees, in the
success branch only:

- `kibana/_sync/client/_base.py:667-677`
- `kibana/_async/client/_base.py:281-291`

Both are byte-identical apart from the word "Async":

```python
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("Request completed successfully with status %s", status)
    # Log response body for debugging (truncate if too large)
    body_str = str(response.body)
    if len(body_str) > 500:
        body_str = body_str[:500] + "... [truncated]"
    logger.debug("Response body: %s", body_str)
```

`str(response.body)` never passes through redaction. The request side, by contrast,
dispatches on type through the machinery added by #78 and #92
(`_base.py:585-590`).

### The machinery to reuse

Single-sourced in the sync tree and imported by async: `_redact_body_secrets` (dicts),
`_redact_body_secrets_sequence` (lists/tuples), `_redact_nested_body_value`
(dispatch + depth cap), `_SENSITIVE_BODY_KEYS`, `_MAX_REDACTION_DEPTH = 20`,
`_REDACTION_DEPTH_LIMIT_PLACEHOLDER`. The fidelity policy is already documented as
log-only (mapping subclasses normalize to `dict`, namedtuples to plain `tuple`) —
which is exactly right for a response log too.

### Design questions the fix must answer

1. **Redact before truncating.** Truncating first and redacting the string afterwards
   cannot work — the machinery operates on structure, not text — and would leak the
   first 500 characters verbatim. Order is forced: redact the object, then `str()`,
   then truncate.
2. **Response bodies are not always dicts or lists.** The request side has three
   branches (dict / list-tuple / raw bytes). A response body may be a dict, a list, a
   scalar, or `None`. The dispatch must cover the same ground without a fourth
   divergent convention.
3. **Truncation threshold and placeholder** should stay as they are (500 chars,
   `"... [truncated]"`) unless there is a reason to change them — that is existing
   observable behavior.
4. **The error branch (`status >= 400`) logs only the extracted error message**, not
   the body, so it is out of scope. Note that the raised exception still carries
   `body=response.body` — that is an exception payload, not a log, and is not what
   #102 is about.

The sync/async parity guard (`tests/unit/test_sync_async_parity.py`) locks method
bodies, so both trees must change together and identically.

---

## 5. Release state

- `kibana/_version.py` = `0.4.2`. Root `CHANGELOG.md` has ~20 `[Unreleased]` bullets,
  **all** under `### Fixed`, at least five of which are behavior-breaking.
- `docs/source/changelog.md` — the second, hand-maintained, Sphinx-published changelog
  — has an **empty** `## Unreleased` and its newest entry is `0.4.2`. The DoD
  `changelog_entry` criterion greps root `CHANGELOG.md` only, so neither the gate nor
  `release.yml` will catch the omission.
- `docs/source/changelog.md:409` still reads `**Current stable**: 0.1.x (when
  released)` — stale since 0.2.0.
- The reordered release pipeline from #82 (validate → build+integration →
  publish-pypi → publish-github-release) has never executed. First live run is
  whatever release comes next. Failure mode to accept up front: PyPI succeeds, GitHub
  release step fails, version is public and unrecallable; recovery is a follow-up
  patch, never a retag.

---

## Open questions for design

1. How should the vocabulary checker be located — vendor the two files back, fetch a
   pinned upstream rev in CI, promote the check into `git-controls-starter` as a
   pinned pre-commit hook, or drop the criterion? The precedent (pinned remote, no
   vendored scripts) and the upstream author's stated model (vendor and execute)
   point in opposite directions.
2. Is the GitHub Actions PR-creation setting something to enable, or should both bot
   workflows be retired/reworked given the de-vendoring?
3. Does the 0.5.0 release wait for #102, or ship without it with a known-limitation
   note?
