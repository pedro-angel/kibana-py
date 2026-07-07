# Evidence — examples live verification for 0.3.1

Captured during the Phase C rework (see
`docs/superpowers/plans/2026-07-07-examples-ux-and-methodology-adoption.md`). This is the
battle-testing artifact for the human-usable-examples change: every example was compile-checked,
and each converted example was exercised **live against the real stack** in its relevant modes.
Reported honestly — where a happy path needed infrastructure the dev stack lacked, the tier and
the missing precondition are named rather than implying a clean run.

## Environment

- **Kibana / Elastic Stack:** 9.4.3 (`elastic-start-local`, `ES_LOCAL_VERSION=9.4.3`)
- **URL:** http://localhost:5601 (status: `available`)
- **Interpreter:** `.venv/bin/python` — CPython 3.14.5
- **Branch:** `feat/kibana-9.4.3-full-api`; Phase C range `8611b77` (C3) … `8d2c3a7` (C9)
- **Auth:** API key from `elastic-start-local/.env` (auto-loaded by `examples/utils.py`)

## Global checks

| Check | Command | Result |
|---|---|---|
| All examples compile | `python -m py_compile examples/*.py` | ✅ all 58 compile |
| Cross-example coexistence (no collision when kept) | `lists_management.py --no-cleanup` + `simple_alerting_rules.py --no-cleanup` | ✅ `kbnpy-lists-bad-ips` and `kbnpy-simple-alerting-rules …` coexist under distinct namespaces |
| Verify teardown reached zero | `… --cleanup` then `client.lists.find()` | ✅ `kbnpy` value lists remaining: ZERO |
| No-TTY safety | `echo "" \| python examples/lists_management.py` | ✅ prints keep notice, exits 0, no crash |
| Idempotent re-run (no 409) | `lists_management.py --no-cleanup` ×2 | ✅ no `ConflictError` |

## Tier legend (per `battle-testing-on-real-infra`)

- **A** — happy path proven live end-to-end.
- **B** — route proven live via its exact semantic rejection (infra/license/flag absent); the real error was asserted, not a crash.
- **C** — could not exercise; missing precondition named. Unit/compile only for that path.

## Per-example results

| Example(s) | Task | Modes exercised live | Tier | Notes |
|---|---|---|---|---|
| `lists_management.py` | C3 | keep / re-run(no-409) / cleanup / no-TTY | A | reference pattern |
| `cases_management.py` (+15 creators compiled) | C4 | keep / re-run(no-409) / cleanup | A | representative of the 16; all 16 compile + ruff clean |
| `agent_builder, simple_saved_object, fleet_outputs, fleet_policies, fleet_enrollment, synthetics, spaces_management, osquery, entity_analytics, timeline` | C5 | all 10 run keep / re-run / cleanup | A | dependency-ordered teardown; caught+fixed a real osquery re-run 409 |
| `simple_space.py`, `async_index_connector.py` (+4 leak-fixes smoke-tested) | C6 | keep / re-run(no-409) / cleanup; async cleanup | A | teardown moved into `finally`; zero orphans after sweep |
| `fleet_epm_management.py` | C7 | happy path ×2 | A | EPR reachable on this stack |
| `maintenance_windows_management.py` | C7 | happy path | A | stack carries a **trial** license (not Basic) |
| `attack_discovery_management.py` | C7 | happy path | A | reverse-order teardown confirmed |
| `security_ai_assistant_management.py` | C7 | conversations / prompts / KB live | A (LLM sub-branch: C) | LLM chat branch skipped — no `KBNPY_LMSTUDIO_OPENAI_URL` |
| `observability_ai_assistant_management.py` | C7 | — | C | cleanly skipped — no LLM connector configured |
| `uptime_management.py`, `fleet_management.py` | C8 | run; restore verified | A | global-state restore in `finally` (uptime 30↔730 days; fleet prerelease→False) |
| `streams_management.py` | C8 | run | B | `403` on `upsert_query` — dev stack lacks `observability:streamsEnableSignificantEvents`; the mid-run error **proved** the `finally` restore fires (child stream deleted, root left as found) |
| `simple_index_connector.py`, `simple_alerting_rules.py` (+5 namespaced) | C9 | keep / re-run(no-409) / cleanup | A | all 7 ran clean; found live 36-char connector-id cap |
| `simple_status, status_management, ml_management, basic_usage, async_*, debug_*, task_manager, upgrade_assistant` (10) | C10 | smoke-run (read-only) | A | create nothing; verified importable/runnable post-fix |

## Bugs found live and fixed (before commit)

1. **`examples/utils.py`** — Python-2 `except ImportError, X:` was a hard `SyntaxError` under 3.14, breaking `import utils` for **every** example. Fixed (C1).
2. **`osquery_management.py`** — idempotent pre-delete used the wrong id field → 409 on re-run. Fixed (C5).
3. **`fleet_epm_management.py`** — `uninstall_package` on a not-installed package raises `BadRequestError`(400), not `NotFoundError`(404); reworked to check `get_package` status first (C7).
4. **`security_ai_assistant_management.py`** — quick-prompt 409 on kept-then-rerun; added own-scope idempotent pre-delete (C7).
5. **`debug_saved_objects.py`** — `with create_span(...)` raised `TypeError` when OTel was off, swallowed by a bare `except: pass`, silently skipping `create()`; replaced with `span_context` + narrowed except (C9).
6. **Connector-id length** — Kibana caps caller-specified connector ids at 36 chars; `{prefix}-connector` (38) was rejected. Ids shortened (C9).

## Honest caveats

- Not every one of the 58 examples was individually driven through all four modes; a representative
  example per conversion group was, and the C5/C6/C7/C9 groups had **every** file run live. The
  remaining creators in C4 were compile+ruff verified with `cases_management.py` as the live
  representative.
- Two paths are tier **C** (LLM connector absent) and one is tier **B** (streams feature flag
  absent). These are environment gaps, not code defects — the examples skip/assert cleanly.
