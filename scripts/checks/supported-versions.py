#!/usr/bin/env python3
"""Keep every statement of the supported Kibana set agreeing with one source.

``kibana/_compat.py`` declares the supported set. Everything else in this
repository that names a Kibana version -- the CI matrixes, the release gate, the
stack template, the README table, the cloud-environment page -- is a *mirror*.
This script is what makes "declared once" true rather than aspirational.

Three modes, each a separate job:

``--check`` (default)
    Every mirror agrees with the source, and every supported line carries a dated
    support decision. Exits non-zero on the first disagreement, naming the file
    and what it expected. This is the gate: ``make versions``, the DoD criterion
    ``versions_consistent``, and the ``checks`` workflow all run it.

``--matrix``
    Print the supported pins as a JSON array for a GitHub Actions matrix. The
    workflows consume this instead of hard-coding versions, which is why the
    matrixes cannot drift -- there is nothing in them to drift. Reads the source
    with :mod:`ast`, so it works on a bare checkout with nothing installed.

``--latest``
    Ask the Elastic container registry what the newest patch of each supported
    line is, and whether a newer minor line exists. This is the "is it time to
    move?" question, answered from the registry rather than from release notes.
    A lookup that cannot reach the registry reports that it could not check --
    never "up to date", which would be a false green.

Exit codes: 0 all good, 1 a check failed, 2 the script could not do its job
(unreadable source, unreachable network under ``--fail-on-drift``).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "kibana" / "_compat.py"

REGISTRY_TOKEN_URL = (
    "https://docker-auth.elastic.co/auth"
    "?service=token-service&scope=repository:kibana/kibana:pull"
)
REGISTRY_TAGS_URL = "https://docker.elastic.co/v2/kibana/kibana/tags/list"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SEMVER_TAG_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


# ---------------------------------------------------------------------------
# Reading the source of truth
# ---------------------------------------------------------------------------


def read_declaration(name: str) -> object:
    """Return a literal assigned at module level in the source, without importing it.

    Importing would need the package installed; the CI job that builds the matrix
    runs before any install. :mod:`ast` also refuses to execute anything, so a
    malformed source is a parse error rather than arbitrary code.
    """
    try:
        tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    except OSError as exc:  # unreadable source is a job failure, not a check failure
        sys.exit(f"FAIL: cannot read {SOURCE}: {exc}")
    except SyntaxError as exc:
        sys.exit(f"FAIL: cannot parse {SOURCE}: {exc}")

    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                if node.value is None:
                    continue
                try:
                    return ast.literal_eval(node.value)
                except ValueError as exc:
                    sys.exit(f"FAIL: {name} in {SOURCE} is not a literal: {exc}")
    sys.exit(f"FAIL: {name} not found in {SOURCE}")


def supported() -> list[tuple[str, str]]:
    """The declared ``(line, pin)`` rows, newest first."""
    value = read_declaration("SUPPORTED_VERSIONS")
    if not isinstance(value, (list, tuple)) or not value:
        sys.exit("FAIL: SUPPORTED_VERSIONS is empty or not a sequence")
    rows: list[tuple[str, str]] = []
    for row in value:
        if not (isinstance(row, (list, tuple)) and len(row) == 2):
            sys.exit(f"FAIL: malformed SUPPORTED_VERSIONS row: {row!r}")
        rows.append((str(row[0]), str(row[1])))
    return rows


# ---------------------------------------------------------------------------
# Mirror checks
# ---------------------------------------------------------------------------


class Report:
    """Accumulates GO/NO-GO lines so one run names every disagreement, not just the first."""

    def __init__(self) -> None:
        self.failed = False

    def ok(self, message: str) -> None:
        print(f"  GO    {message}")

    def bad(self, message: str) -> None:
        print(f"  NO-GO {message}")
        self.failed = True


def _read(path: Path, report: Report) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        report.bad(f"{path.relative_to(REPO)}: unreadable ({exc})")
        return None


def check_env_template(rows: list[tuple[str, str]], report: Report) -> None:
    """The stack template pins the newest supported patch.

    The template is what a fresh clone and every un-overridden ``ci-stack-up.sh``
    run bring up, so it tracks the newest pin rather than an arbitrary one.
    """
    path = REPO / "elastic-start-local" / ".env.example"
    text = _read(path, report)
    if text is None:
        return
    want = rows[0][1]
    found = re.search(r"^ES_LOCAL_VERSION=(\S+)$", text, re.M)
    if found is None:
        report.bad(f"{path.relative_to(REPO)}: no ES_LOCAL_VERSION line")
    elif found.group(1) != want:
        report.bad(
            f"{path.relative_to(REPO)}: ES_LOCAL_VERSION={found.group(1)}, expected {want}"
        )
    else:
        report.ok(f"{path.relative_to(REPO)}: ES_LOCAL_VERSION={want}")


def check_cloud_setup(rows: list[tuple[str, str]], report: Report) -> None:
    """The cloud setup script pre-pulls exactly the supported pins, newest first."""
    path = REPO / "scripts" / "cloud-setup.sh"
    text = _read(path, report)
    if text is None:
        return
    want = " ".join(pin for _line, pin in rows)
    found = re.search(r'KIBANA_PY_STACK_VERSIONS:-([^}"]+)', text)
    if found is None:
        report.bad(f"{path.relative_to(REPO)}: no KIBANA_PY_STACK_VERSIONS default")
    elif found.group(1).strip() != want:
        report.bad(
            f"{path.relative_to(REPO)}: KIBANA_PY_STACK_VERSIONS default is "
            f"'{found.group(1).strip()}', expected '{want}'"
        )
    else:
        report.ok(f"{path.relative_to(REPO)}: pre-pull default '{want}'")


def check_readme_table(rows: list[tuple[str, str]], report: Report) -> None:
    """The README "Version support" table lists every line at its pin, and nothing else."""
    path = REPO / "README.md"
    text = _read(path, report)
    if text is None:
        return
    table = re.findall(r"^\|\s*(\d+\.\d+)\.x\s*\|\s*(\d+\.\d+\.\d+)\s*\|", text, re.M)
    if not table:
        report.bad(f"{path.relative_to(REPO)}: no version-support table rows found")
        return
    if table != [(line, pin) for line, pin in rows]:
        report.bad(
            f"{path.relative_to(REPO)}: version-support table is {table}, "
            f"expected {[(line, pin) for line, pin in rows]}"
        )
    else:
        report.ok(f"{path.relative_to(REPO)}: version-support table matches")


def check_cloud_environment_doc(rows: list[tuple[str, str]], report: Report) -> None:
    """The cloud-environment page's env-var block names the supported pins."""
    path = REPO / "docs" / "source" / "development" / "cloud-environment.md"
    text = _read(path, report)
    if text is None:
        return
    want = " ".join(pin for _line, pin in rows)
    found = re.search(r"^KIBANA_PY_STACK_VERSIONS=(.+)$", text, re.M)
    if found is None:
        report.bad(f"{path.relative_to(REPO)}: no KIBANA_PY_STACK_VERSIONS block")
    elif found.group(1).strip() != want:
        report.bad(
            f"{path.relative_to(REPO)}: KIBANA_PY_STACK_VERSIONS={found.group(1).strip()}, "
            f"expected {want}"
        )
    else:
        report.ok(f"{path.relative_to(REPO)}: environment block matches")


def check_workflows_have_no_literals(report: Report) -> None:
    """No workflow hard-codes a stack version.

    The matrixes are generated from the source (``--matrix``), so a literal
    ``9.x.y`` in a workflow is by definition a copy that can drift. Comments are
    exempt: they explain history and often must name a version.
    """
    for name in ("integration-probe.yml", "release.yml"):
        path = REPO / ".github" / "workflows" / name
        text = _read(path, report)
        if text is None:
            continue
        offenders = []
        for number, line in enumerate(text.splitlines(), start=1):
            code = line.split("#", 1)[0]
            if re.search(r"\b9\.\d+\.\d+\b", code):
                offenders.append(f"{number}: {line.strip()}")
        if offenders:
            report.bad(
                f"{path.relative_to(REPO)}: hard-coded stack version(s) — generate the "
                f"matrix from {SOURCE.relative_to(REPO)} instead:\n      "
                + "\n      ".join(offenders)
            )
        else:
            report.ok(f"{path.relative_to(REPO)}: no hard-coded stack versions")


def check_support_decisions(rows: list[tuple[str, str]], report: Report) -> None:
    """Every supported line carries a dated decision saying why it is still here.

    This is the check that makes the oldest line's continued support a choice
    rather than an oversight: a new line cannot be added without a row, and the
    older line's row is what proves its review actually happened.
    """
    decisions = read_declaration("SUPPORT_DECISIONS")
    if not isinstance(decisions, (list, tuple)):
        report.bad("SUPPORT_DECISIONS is not a sequence")
        return
    by_line = {}
    for row in decisions:
        if not (isinstance(row, (list, tuple)) and len(row) == 4):
            report.bad(f"malformed SUPPORT_DECISIONS row: {row!r}")
            return
        line, verdict, date, reason = (str(part) for part in row)
        if not _DATE_RE.match(date):
            report.bad(f"SUPPORT_DECISIONS[{line}]: date '{date}' is not YYYY-MM-DD")
        if verdict not in {"added", "kept"}:
            report.bad(
                f"SUPPORT_DECISIONS[{line}]: verdict '{verdict}' is neither 'added' nor 'kept'"
            )
        if len(reason.strip()) < 40:
            report.bad(
                f"SUPPORT_DECISIONS[{line}]: reason is too short to be a real decision"
            )
        by_line[line] = verdict

    for line, _pin in rows:
        if line not in by_line:
            report.bad(
                f"SUPPORT_DECISIONS has no row for supported line {line} — a line may not "
                "join the set without a recorded, dated reason"
            )
    extra = set(by_line) - {line for line, _pin in rows}
    if extra:
        report.bad(
            f"SUPPORT_DECISIONS names {sorted(extra)}, which is not in SUPPORTED_VERSIONS "
            "— move a dropped line's row to the version-support page's history table"
        )
    if not report.failed:
        report.ok(f"support decisions recorded for {', '.join(by_line)}")

    oldest = rows[-1][0]
    if by_line.get(oldest) == "added" and len(rows) > 1:
        report.bad(
            f"the oldest supported line {oldest} is recorded as 'added', not 'kept' — "
            "adding a newer line requires re-deciding the oldest one and recording the verdict"
        )


# ---------------------------------------------------------------------------
# Upstream currency
# ---------------------------------------------------------------------------


def registry_tags(timeout: float) -> list[tuple[int, int, int]] | None:
    """Released Kibana versions from the Elastic registry, or ``None`` if unreachable.

    ``None`` is the important return: it means "not checked", and every caller
    must report it as such rather than folding it into "nothing newer".
    """
    try:
        with urllib.request.urlopen(REGISTRY_TOKEN_URL, timeout=timeout) as response:
            token = json.load(response).get("token")
        if not token:
            return None
        request = urllib.request.Request(
            REGISTRY_TAGS_URL, headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            tags = json.load(response).get("tags", [])
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        return None

    out = []
    for tag in tags:
        match = _SEMVER_TAG_RE.match(tag)
        if match:
            out.append(tuple(int(part) for part in match.groups()))
    return sorted(out) or None


def report_currency(rows: list[tuple[str, str]], timeout: float) -> int:
    """Compare the pins against the registry. Returns the number of drifts found."""
    released = registry_tags(timeout)
    if released is None:
        print(
            "  UNKNOWN  could not reach the Elastic registry — currency NOT checked.\n"
            "           This is not 'up to date'. Re-run with network access."
        )
        return -1

    drift = 0
    for line, pin in rows:
        major, minor = (int(part) for part in line.split("."))
        patches = [version for version in released if version[:2] == (major, minor)]
        if not patches:
            print(f"  UNKNOWN  {line}: no released patch found in the registry")
            continue
        newest = ".".join(str(part) for part in patches[-1])
        if newest != pin:
            print(f"  DRIFT    {line}: pinned {pin}, latest released {newest}")
            drift += 1
        else:
            print(f"  CURRENT  {line}: {pin} is the latest patch")

    supported_lines = {tuple(int(p) for p in line.split(".")) for line, _pin in rows}
    newer = sorted({version[:2] for version in released} - supported_lines)
    newest_supported = max(supported_lines)
    newer = [line for line in newer if line > newest_supported]
    if newer:
        names = ", ".join(f"{major}.{minor}" for major, minor in newer)
        print(
            f"  NEW LINE {names} released and not in the supported set.\n"
            "           Adding it requires re-deciding the OLDEST supported line —\n"
            "           see docs/source/development/version-support.md."
        )
        drift += len(newer)
    return drift


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="verify every mirror agrees with the source (default)",
    )
    mode.add_argument(
        "--matrix", action="store_true", help="print the supported pins as JSON"
    )
    mode.add_argument(
        "--latest",
        action="store_true",
        help="ask the registry whether newer patches or lines exist",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="with --latest, exit non-zero when the pins are behind",
    )
    parser.add_argument(
        "--timeout", type=float, default=20.0, help="registry timeout in seconds"
    )
    args = parser.parse_args()

    rows = supported()

    if args.matrix:
        print(json.dumps([pin for _line, pin in rows]))
        return 0

    if args.latest:
        print(f"Kibana support currency (source: {SOURCE.relative_to(REPO)})")
        drift = report_currency(rows, args.timeout)
        if args.fail_on_drift and drift != 0:
            return 1
        return 0

    print(f"Supported-version consistency (source: {SOURCE.relative_to(REPO)})")
    print(f"  declared: {', '.join(f'{line}.x @ {pin}' for line, pin in rows)}")
    report = Report()
    check_support_decisions(rows, report)
    check_env_template(rows, report)
    check_cloud_setup(rows, report)
    check_readme_table(rows, report)
    check_cloud_environment_doc(rows, report)
    check_workflows_have_no_literals(report)
    if report.failed:
        print("\nNO-GO: a version statement disagrees with the source above.")
        return 1
    print("\nGO: every version statement agrees with the source.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
