# Human-usable examples with keep/clean and non-colliding resources

- **Date:** 2026-07-07
- **Version:** v0.3 (v0.1 → v0.2: aligned to `pedro-angel/agent-methodology` skills; v0.2 → v0.3:
  reconciled onto shipped code — see *Reconciliation (v0.3)*)
- **Target release:** `0.3.1` (patch)
- **Status:** Shipped. Reconciled to the delivered examples.

## Reconciliation (v0.3 — onto shipped code)

Implemented and live-verified against Kibana 9.4.3. Divergences/refinements from the v0.2 design,
per `spec-driven-development` (record what actually shipped):

- **Idempotent start, universalized.** v0.2 described idempotent-start as "delete-if-exists before
  create" for fixed-id resources. Shipped reality: *every* resource-creating example is idempotent
  on re-run, via one of two own-scope mechanisms — (a) a **stable caller-chosen id + pre-delete**
  where the API accepts one (lists, spaces, connectors, alerting rules, data views, fleet outputs,
  …), or (b) a **find-by-prefix cleanup** of the example's own `kbnpy-<slug>-*` resources where the
  id is server-assigned (visualizations, cases, slos, dashboards, maintenance windows, endpoint
  scripts, attack-discovery schedules). Both never touch anything outside the example's own prefix.
- **Deliberate exception:** `error_handling.py` intentionally creates a duplicate to demonstrate
  `ConflictError` handling, so it does *not* pre-delete — documented as the sole exception in
  `examples/README.md` and the CHANGELOG.
- **Live-found fixes folded in** (the running system is ground truth, per `battle-testing-on-real-infra`):
  the `utils.py` Python-2 `except` SyntaxError; osquery re-run 409 (wrong id field); fleet_epm
  `uninstall_package` returning 400-not-404 on a not-installed package; security_ai quick-prompt 409;
  `debug_saved_objects` silent create-swallow (`create_span` `TypeError`); the 36-char connector-id
  cap; and the attack-discovery schedule-name/prefix mismatch. Follow-up passes F1–F3 (after the
  original C1–C10) closed the accumulation on all server/uuid-id examples.
- **Evidence:** `docs/evidence/examples-0.3.1.md`.

## Problem

The example scripts under `examples/` exist for humans to run, watch the
results, and *then* decide whether to keep or delete the resources they created.
That flow works in the first-generation examples but was lost in the newer ones:

- **Gen 1 (12 scripts)** call `should_cleanup()` (`examples/utils.py:677`), which
  prompts `Delete created resources? (y/N)` at the end and honours
  `--cleanup` / `--no-cleanup`. This is the intended human flow.
- **Gen 2 (~29 `*_management.py`)** wrap their work in `try/finally:` that
  **unconditionally deletes** every created resource at the end (e.g.
  `examples/lists_management.py:75-82`). They run act→clean end-to-end like an
  integration test, giving a human no chance to inspect what was created.

Two secondary problems compound this:

1. **Resource-name collisions.** Gen 2 uses fixed literal IDs. Many already
   carry a per-example prefix, but ~19 fall back to a generic `kbnpy-example-*`
   namespace. If a human keeps resources, IDs can collide *across* examples, and
   **re-running any kept example collides with itself** (fixed ID → HTTP 409).
2. **A blocking SyntaxError.** `examples/utils.py` lines 329/335/341 use the
   Python 2 form `except ImportError, Exception:`, which is a hard `SyntaxError`
   under Python 3.14. Because every example does `from utils import ...`, this
   currently breaks *all* utils-importing examples. Verified via
   `python -m py_compile examples/utils.py`.

## Why this is a patch release

Example scripts are **not part of the distributed package**. The wheel packs
`packages = ["kibana"]` only; the sdist includes `/kibana/**` + README/LICENSE/
NOTICE; and `.github/workflows/release.yml:75` actively asserts that `examples/`,
`tests/`, and `docs/` must **not** appear in the wheel. SemVer governs the public
API of the shipped artifact, and these changes touch only repo-local example
scripts plus their shared helper. Therefore this is a **patch → `0.3.1`**, not a
minor. (Only changes to `kibana/` library code would force `0.4.0`; this work
must not touch it.)

## Goals

1. Every example that creates resources lets a human **watch results first, then
   choose** to delete or keep — one prompt, at the end.
2. Kept resources **never collide across examples**, and **re-running the same
   example is always safe** (idempotent, no 409).
3. Fix the `utils.py` SyntaxError so examples import at all.
4. Uniform behaviour and naming across the whole `examples/` tree (58 scripts).

## Non-goals

- No changes to `kibana/` library code or the public API.
- No wiring of examples into CI (they remain human-run; verification is manual /
  local against `elastic-start-local`).
- No new dependencies.

## Design

### 1. Standard example skeleton

Every example that creates resources adopts this shape:

```python
created = []                          # (kind, id) in creation order
try:
    _ensure_absent(client, "list", list_id)   # delete-if-exists, swallow NotFoundError
    client.lists.create(id=list_id, ...)      # then create fresh
    created.append(("list", list_id))
    ...                                        # act + print results for the human
finally:
    if should_cleanup():                       # ONE prompt, AFTER results
        for kind, _id in reversed(created):
            _delete(client, kind, _id)         # swallow NotFoundError
    else:
        print_kept(created)                    # "Kept … — re-run with --cleanup to remove"
    client.close()
```

Key properties:

- **Idempotent start** (`_ensure_absent`) is what makes re-running-after-keep
  safe: any leftover from a prior kept run is removed before recreating, so a
  second run can never 409. This realises the chosen "idempotent, stable names"
  strategy.
- **Own only your scope** (`secrets-and-teardown-discipline`). Both the
  idempotent pre-delete and the final cleanup operate *exclusively* on ids the
  example itself created under its own `kbnpy-<slug>-*` namespace. An example
  never deletes, and must not be able to delete, a resource it did not create —
  no "delete everything matching a broad glob," no touching user data. The
  derived prefix is the mechanical scope boundary.
- **One prompt at the end** via the existing `should_cleanup()`: the human sees
  all output first, then decides. `--cleanup` / `--no-cleanup` still override for
  scripted / non-interactive runs.
- **Reversible by default** (`reversible-by-default-confirm-consequential`). The
  deletion is the consequential, hard-to-undo act, so it is gated behind an
  explicit confirmation; the default (bare Enter, or no TTY) is **keep** — the
  reversible outcome that destroys nothing. Deleting is a deliberate `y` /
  `--cleanup`. On keep, `print_kept()` stages exactly what remains *and* the exact
  command to remove it later, so the human's next action is logged and obvious.
  (Confirmed with the user.)

Async examples use the same structure with `await`ed deletes; the sync
`should_cleanup()` prompt is called from the async `main()` and is acceptable to
block on in an example.

### 2. Naming convention

`kbnpy-<example-slug>-<resource>`, one distinct slug per file — e.g.
`kbnpy-lists-bad-ips`, `kbnpy-detection-rule`, `kbnpy-fleet-agents-...`. This:

- guarantees kept resources never collide *across* examples, and
- keeps names predictable and greppable/findable in the Kibana UI (the whole
  point of a human keeping them).

**Derive the slug from the filename, don't duplicate it** (`configuration-single-source-of-truth`):
a `resource_prefix(__file__)` helper in `utils.py` returns `kbnpy-<stem>` where `<stem>` is the
example's filename with a trailing `_management` stripped (`lists_management.py` → `kbnpy-lists`).
Each example builds its ids off that one value, so the namespace can never drift from the
file that owns it — and the prefix *is* the example's scope marker (see the teardown invariant
below).

This replaces the ~19 generic `kbnpy-example-*` identifiers. Gen 1 examples get
the same convention in a naming pass even though their cleanup already prompts.

### 3. `utils.py` changes (bugfix + hardening — ship in this patch)

- **Fix the SyntaxError:** rewrite `_get_opentelemetry_version()` so the three
  `except ImportError, Exception:` / `except ImportError, AttributeError:` clauses
  become correct single-type fallbacks (`except Exception:`), preserving the
  intended sdk → api → module-`__version__` → `"unknown"` fallback chain.
- **Harden `should_cleanup()`:** when `sys.stdin` is not a TTY
  (`not sys.stdin.isatty()`), skip `input()` and default to **keep**
  (return `False`) with a short printed note, instead of raising `EOFError`.
  `--cleanup` / `--no-cleanup` still take precedence.
- **Add `resource_prefix(file)`** helper: returns `kbnpy-<stem>` from an example's
  `__file__` (stripping a trailing `_management`), so the per-example namespace is
  derived once from the filename rather than duplicated as a literal in each script
  (`configuration-single-source-of-truth`).
- **Add `print_kept(created)`** helper: given the `(kind, id)` list, prints a
  consistent "Kept the following resources … re-run with `--cleanup` to remove"
  summary, so all ~58 files share one message and stay readable.
- Optionally add thin `_ensure_absent` / `_delete` dispatch helpers *only* if a
  clean, readable form emerges; otherwise keep delete/pre-delete inline per
  example (readability of a standalone example beats DRY). Decide during
  implementation, not upfront.

### 4. Documentation & release

- `examples/README.md`: document the watch → keep/clean flow, the
  `--cleanup` / `--no-cleanup` flags, the `kbnpy-<example>-<resource>` naming
  convention, and that re-running is safe/idempotent. Present-tense, verified
  against the running examples (`docs-as-deliverable`).
- `CHANGELOG.md`: add a `## [0.3.1] - 2026-07-07` entry under Fixed/Changed
  covering the SyntaxError fix and the human-usable example rework.
- `kibana/_version.py`: bump `__versionstr__` to `0.3.1`.

**Commit plan** (`surgical-changes-with-checkpoints` — split by reason, one motivation
each, conventional prefix, provenance trailer, leave uncommitted until the user wants to
inspect):

1. `fix(examples): repair Python-2 except syntax in utils.py` — the blocking bugfix, on its own.
2. `refactor(examples): human keep/clean flow + per-example resource namespacing` — the UX rework.
3. `docs: document example keep/clean workflow; release 0.3.1` — README, CHANGELOG, version bump.

Commit 2 (or whichever rests on the live run) carries an `Evidence:` trailer pointing at the
`docs/evidence/` artifact.

## Affected files

- **58 example scripts** (`examples/*.py`, excluding `utils.py`), split by a
  per-file audit (see Implementation notes) into:
  - *creates resources* → full skeleton + naming conversion;
  - *read-only* (e.g. `simple_status.py`, `status_management.py`, `debug_*`,
    `task_manager_management.py`, `uptime_management.py`) → no cleanup change;
    consistency review only.
- `examples/utils.py` — SyntaxError fix, `should_cleanup()` TTY hardening,
  `print_kept()` (+ optional dispatch helpers).
- `examples/README.md`, `CHANGELOG.md`, `kibana/_version.py`.

## Implementation notes

- **Per-file audit is the first task.** A grep for `.delete(` under-counts
  (misses `.delete_role()`, `.bulk_action()`, `.archive()`, etc.), so each
  example must be read to classify it (read-only vs creates-resources), list the
  resources it creates, and note its current cleanup path. This audit drives the
  edit list.
- Some examples deliberately *leave* infrastructure-ish state or create objects
  they never delete (e.g. detection rules, roles); bring these under the same
  keep/clean prompt rather than assuming they are read-only.

## Verification

Examples are not in CI, so verification is a manual **live** run against the local
`elastic-start-local` stack — done means validated live, end-to-end
(`battle-testing-on-real-infra`), not "mocks are green":

1. `python -m py_compile examples/*.py` — all compile (proves the SyntaxError is
   gone and no conversion introduced a new one).
2. Run a representative subset (sync + one async) live in each mode:
   - default → keep (inspect that resources remain);
   - `--cleanup` → all deleted;
   - `--no-cleanup` → all kept;
   - **re-run after a kept run** → succeeds with no 409 (proves idempotent start);
   - **piped / no-TTY run** → does not crash, defaults to keep.
3. Confirm kept resources from two different examples coexist without collision.
4. **Verify teardown reached zero, don't assume it** (`secrets-and-teardown-discipline`):
   after a `--cleanup` run, query the server and assert no `kbnpy-<slug>-*` resources
   for that example survive — the delete is confirmed against reality, not inferred from
   a swallowed exception.
5. **Rank each example into the three live tiers** (`battle-testing-on-real-infra`):
   happy-path proven live > route proven live via its exact semantic rejection (for
   examples that need infra the dev stack lacks — an enrolled agent, a Defend endpoint,
   a cloud account) > unit-only with the missing precondition named. Only the third tier
   counts as untested against reality; a path that names no missing precondition is a
   hole pretending to be covered.

**Evidence artifact.** Capture the run as a machine-readable file under
`docs/evidence/` (e.g. `examples-0.3.1.md` or `.json`) pinning: the exact commands, the
Kibana version and URL, and a per-example / per-mode PASS. Reference it from an `Evidence:`
trailer on the commit whose correctness rests on the run (`surgical-changes-with-checkpoints`),
so the proof travels with the commit instead of living in this conversation. Report only what
was measured (`honest-reframing-over-overclaiming`) — if a subset was run rather than all 58,
say which, rather than implying full coverage.

## Methodology alignment

This spec adopts `pedro-angel/agent-methodology` — fittingly, since that pack was distilled
partly from *this* build (a REST client covering an external system's full API against a live
server). Mapping of skill → where it lands:

| Skill | Applied as |
| --- | --- |
| `spec-driven-development` | This versioned spec, reviewed before build; reconcile onto shipped code + bump version on divergence; strike-through (not delete) resolved opens. |
| `reversible-by-default-confirm-consequential` | Deletion gated behind explicit `y`/`--cleanup`; default = keep (destroys nothing); `print_kept()` stages the exact undo command. |
| `secrets-and-teardown-discipline` | Own-only-your-scope teardown (never touch non-`kbnpy-<slug>` ids); verify-teardown-reached-zero in the verification run. |
| `configuration-single-source-of-truth` | `resource_prefix(__file__)` derives the namespace from the filename instead of a per-file literal. |
| `battle-testing-on-real-infra` | Live run against the real stack, captured as a `docs/evidence/` artifact; three-tier ranking for infra-gated paths. |
| `surgical-changes-with-checkpoints` | Bugfix / rework / docs split into separate commits with provenance + `Evidence:` trailers; uncommitted until the user inspects. |
| `honest-reframing-over-overclaiming` | Report the subset actually run; don't imply full-58 coverage unless every one was exercised. |
| `docs-as-deliverable` | README/CHANGELOG present-tense and verified against the running examples. |

**Out of scope for `0.3.1`** (proposed as separate follow-ups, not folded into this patch, per
`surgical-changes`): installing the methodology pack into the repo (`AGENTS.md` + `skills/` +
`CLAUDE.md`); adding git-controls commit discipline (conventional-prefix, provenance-trailer,
`detect-private-key`, no-tracked-secrets hooks); and SHA-pinning `release.yml`'s actions before
the next PyPI publish.

## Open questions

None. Both decision points (idempotent stable names; apply to all examples) and
both gut-checks (default-on-Enter = keep; SyntaxError fix in-scope for `0.3.1`)
are confirmed.
