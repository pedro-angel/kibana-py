# Kibana Version Support

This page is the maintenance framework for the versions of Kibana `kibana-py` supports:
the policy, the single place the set is declared, the procedure for moving it forward,
and the decision that procedure forces someone to make.

It exists because "support the latest two lines" is easy to write and easy to stop
doing. Kibana ships a minor line roughly every eight weeks. Without a procedure the
supported set becomes whatever it was when someone last looked, and the README slowly
turns into a claim nobody is testing.

## The policy

**The two most recent Kibana minor lines, at the latest patch of each.**

- Older patches of a supported line are expected to work. They are not tested, and the
  client does not claim them.
- A line is supported only if the release gate blocks on it. "Supported but not gated"
  is not a state this repository has — see [the gate](#the-gate) below.
- Support is never extended by inertia. When a new line appears, the oldest supported
  line is **re-decided**, and the verdict is recorded with a date.

## Where the set is declared

One place: `SUPPORTED_VERSIONS` in `kibana/_compat.py`.

```python
SUPPORTED_VERSIONS = (
    ("9.5", "9.5.2"),
    ("9.4", "9.4.5"),
)
```

Everything else that names a Kibana version is a **mirror**, and mirrors are never
authored by hand twice. They are handled in exactly one of two ways:

| Mirror | How it stays true |
| :--- | :--- |
| `.github/workflows/integration-probe.yml` matrix | **derived** — a `versions` job runs `supported-versions.py --matrix` |
| `.github/workflows/release.yml` gate matrix | **derived** — same |
| `scripts/integration-matrix.sh` (the local gate's loop) | **derived** — same, so `make test-integration-matrix` and `make dod` cover a new line with no edit |
| `elastic-start-local/.env.example` (`ES_LOCAL_VERSION`) | **checked** against the newest pin |
| `scripts/cloud-setup.sh` (pre-pull default) | **checked** against all pins, newest first |
| `README.md` "Version support" table | **checked** row by row |
| `docs/source/development/cloud-environment.md` env block | **checked** |

The set also ships in the wheel, because it answers a runtime question:

```python
>>> from kibana import Kibana, is_supported, SUPPORTED_VERSIONS
>>> client = Kibana("http://localhost:5601", api_key="...")
>>> client.server_version()
'9.5.2'
>>> is_supported(client.server_version())
True
>>> SUPPORTED_VERSIONS
(('9.5', '9.5.2'), ('9.4', '9.4.5'))
```

(async: `await client.server_version()`.)

## The gate

```bash
make versions
```

runs `scripts/checks/supported-versions.py`, which fails if any mirror disagrees with
the source, if a workflow has re-grown a hard-coded version, or if a supported line has
no dated support decision. It is a required Definition-of-Done criterion
(`versions_consistent` in `dod.config`) and runs in the `checks` workflow, so drift
cannot merge.

`make versions` proves the *statements* agree. What proves the *client* agrees is the
integration suite running against every line in the set — in CI as the release gate's
matrix, and locally as `make test-integration-matrix`, which the `integration_green`
Definition-of-Done criterion runs. Both build their version list from `--matrix` below,
so "supported but not gated" cannot be reached by forgetting a line: adding one to
`kibana/_compat.py` adds it to both gates.

Two other modes:

```bash
python3 scripts/checks/supported-versions.py --matrix   # JSON pins, for CI
python3 scripts/checks/supported-versions.py --latest   # ask the registry what exists
```

`--latest` is the currency check. It queries the Elastic container registry — the same
place the stack images come from — rather than release notes, so a patch that exists is
detected the day it is published:

```text
Kibana support currency (source: kibana/_compat.py)
  CURRENT  9.5: 9.5.2 is the latest patch
  CURRENT  9.4: 9.4.5 is the latest patch
```

When the registry cannot be reached it prints `UNKNOWN ... currency NOT checked` and
says so explicitly. That is deliberate: a failed lookup reported as "up to date" is the
exact false green this framework exists to prevent.

## The procedure: a new Kibana line has appeared

```{mermaid}
flowchart TB
    detect["--latest reports a new line"] --> decide{"Should the OLDEST<br/>supported line stay?"}
    decide -->|"keep — record 'kept' + reason + date"| two["Set becomes: new line + previous newest<br/>oldest drops off"]
    decide -->|"drop deliberately — record why on this page"| two
    two --> probe["Bring the new pin up live.<br/>Run the integration suite against it."]
    probe --> diff{"Divergences?"}
    diff -->|none| declare
    diff -->|"response shape"| norm["Add an additive normalizer in _compat.py"]
    diff -->|"contested request field"| shapefix["Add a CAPABILITIES row for the field;<br/>send it only where it is accepted"]
    diff -->|"endpoint removed"| cap["Add a CAPABILITIES row + gate the method"]
    norm --> declare
    shapefix --> declare
    cap --> declare
    declare["Update SUPPORTED_VERSIONS + SUPPORT_DECISIONS"] --> gatecheck["make versions — fix every mirror it names"]
    gatecheck --> evidence["Run both pins live; commit the evidence artifact"]
    evidence --> dod["make dod → GO"]
```

Step by step:

1. **Detect.** `python3 scripts/checks/supported-versions.py --latest`, or the failure
   of that check in a scheduled run.
2. **Decide about the oldest line.** This is the step that must not be skipped; see
   [the decision](#the-decision-should-the-oldest-line-still-be-supported) below.
3. **Probe the new pin live.** Bring the stack up
   (`ES_LOCAL_VERSION=<pin> ./scripts/ci-stack-up.sh`) and run
   `tests/integration/`. Read the failures as findings about the *client*.
4. **Classify each divergence** by the three kinds in the diagram, and fix it with the
   matching mechanism. The design rationale for each is in
   `docs/superpowers/specs/2026-08-21-multi-version-support-design.md`.
5. **Declare** the new set in `SUPPORTED_VERSIONS`, with a `SUPPORT_DECISIONS` row for
   every line.
6. **Run `make versions`** and fix each mirror it names. The CI matrixes need no edit.
7. **Battle-test both pins** and commit the evidence file under `docs/evidence/`.
8. **`make dod`** must report GO before the change is claimed done.

### Moving a patch forward within a supported line

Steps 1, 5, 6, 7, 8 only — a patch bump needs no support decision, but it does need a
live run. A patch is not "obviously safe": 9.5.1 → 9.5.2 is exactly the kind of hop
where a preview API changes shape.

## The decision: should the oldest line still be supported?

Adding a line is the moment to ask whether the oldest one still earns its place. The
answer is not automatically yes, and it is not automatically no — but it must be
**recorded**, because the failure mode this framework guards against is not a wrong
answer, it is nobody asking.

The gate enforces the asking. `SUPPORT_DECISIONS` must carry a row for every supported
line, and the *oldest* line's verdict must read `kept` rather than `added`. A verdict of
`kept` can only be written by someone who considered dropping it.

### Criteria

Weigh these; any one can carry the decision.

| Criterion | Drop the line when… |
| :--- | :--- |
| **Upstream maintenance** | Elastic no longer supports it. The client should not outlive the server's own support window. |
| **Divergence cost** | Keeping it forces a genuinely *branched* code path — different requests, different logic — rather than additive normalization. Forked paths are where multi-version clients rot. |
| **Blocked fixes** | A change the newer line needs cannot be made without breaking the older one. |
| **Demand** | Nobody is on it. Weakest criterion, and never sufficient alone: absence of reports is not absence of users. |
| **Gate cost** | The release gate has become slow or flaky enough on that line to be a tax on every release, and the cause is the line rather than the tests. |

Keeping a line is the default when none of these fires and the client's compatibility
layer for it stays additive.

### The record

| Date | Line | Verdict | Reason |
| :--- | :--- | :--- | :--- |
| 2026-08-21 | 9.5 | added | Newest released line. Joined at 9.5.2 once the two divergences from it — the dashboards search envelope and the significant-events rename — were absorbed and both lines ran green live. |
| 2026-08-21 | 9.4 | **kept** | Reviewed when 9.5 joined. Kept: it is the older of exactly two lines, so dropping it would leave the client single-version — the thing this framework exists to prevent — and none of the drop criteria fires. The cost of keeping it is bounded: the compatibility layer is version-free normalization plus two gated endpoints, not a forked code path. |

Dropped lines keep their row here. Deleting the record would erase the reasoning that a
future maintainer needs when the same question comes round.

## What a divergence looks like, and what to do with it

Four kinds seen so far, absorbed by two mechanisms. The full rationale is in the design
doc; this is the working summary.

| Kind | Example found in 9.5 | Mechanism | Needs to know the version? |
| :--- | :--- | :--- | :--- |
| Response renamed or rewrapped | `GET /api/dashboards` moved from `{dashboards, page, total}` to `{data, meta{…}}` | an additive normalizer in `_compat.py` — add the missing spelling, remove nothing | no |
| Response key renamed | significant events: `significant_events` → `queries` | same | no |
| A field one line requires and the other rejects | `queries` in a stream upsert body — 9.4 requires it, 9.5 rejects it | a `CAPABILITIES` row for the **field**, checked before the body is built | yes |
| Endpoint removed | significant-events `_generate` and `_preview` | a `CAPABILITIES` row plus `_require_capability()` in the method | yes |

The rule that survives measurement: **responses can be absorbed without knowing the
version, requests cannot.** A response's shape discriminates itself; a request has to be
chosen before the server can object.

Even so, the client has no version-branched *code path* — one field and two methods each
resolve through the same `CAPABILITIES` table lookup, and everything else is identical on
both lines.

## Untested is not unsupported, and both are stated

The client is tested against the pins and nothing else. Two honest consequences:

- **Other patches of a supported line** — `is_supported()` returns `True` for them,
  because the client's compatibility work is per-line. They are not tested, and the
  README says so.
- **Anything outside the supported set** — the client does not refuse to talk to it.
  `_require_capability()` fails open on an unrecognised version precisely because the
  client has measured nothing about that server and should not pretend otherwise.
  Calls behave exactly as they did before this framework existed: the server answers.
