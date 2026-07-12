#!/usr/bin/env python3
"""Aggregate per-test outcomes across N JUnit files into a flake report.

Distinguishes FLAKY (passed in some runs, failed/errored in others) from
ALWAYS-FAIL (deterministic -- e.g. the ELSER Knowledge Base tests, #28) so a
known-red test does not masquerade as flake, and vice-versa.

Anti-greenwash: exits non-zero ONLY when nothing executed. It does NOT gate on
failures -- the probe measures, it does not judge. (Seeds the DoD #30 assertion.)

Usage: flake_rate.py <junit_dir> <github_step_summary_path>
"""

import glob
import os
import sys
from collections import defaultdict
from xml.etree import ElementTree as ET

junit_dir, summary_path = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(junit_dir, "run-*.xml")))
runs = len(files)

seen: dict[str, dict[str, int]] = defaultdict(
    lambda: {"pass": 0, "fail": 0, "error": 0, "skip": 0}
)
total_cases = 0
for path in files:
    for testcase in ET.parse(path).getroot().iter("testcase"):
        name = f'{testcase.get("classname")}::{testcase.get("name")}'
        total_cases += 1
        tags = {child.tag for child in testcase}
        if "failure" in tags:
            seen[name]["fail"] += 1
        elif "error" in tags:
            seen[name]["error"] += 1
        elif "skipped" in tags:
            seen[name]["skip"] += 1
        else:
            seen[name]["pass"] += 1

if runs == 0 or total_cases == 0:
    sys.stderr.write(
        "FATAL: no JUnit testcases found -- the selection executed nothing.\n"
    )
    sys.exit(2)

flaky = {n: c for n, c in seen.items() if c["pass"] and (c["fail"] or c["error"])}
always_fail = {
    n: c for n, c in seen.items() if not c["pass"] and (c["fail"] or c["error"])
}


def row(name: str, counts: dict[str, int]) -> str:
    return (
        f'  {counts["pass"]}/{runs} pass  '
        f'fail={counts["fail"]} err={counts["error"]} skip={counts["skip"]}  {name}'
    )


with open(summary_path, "a") as summary:
    summary.write(f"\n## Flake report -- {runs} run(s), {len(seen)} distinct tests\n\n")
    summary.write(f"- **FLAKY (nondeterministic):** {len(flaky)}\n")
    summary.write(f"- **ALWAYS-FAIL (deterministic):** {len(always_fail)}\n\n")
    if flaky:
        body = "\n".join(row(n, c) for n, c in sorted(flaky.items()))
        summary.write(f"### Flaky\n```\n{body}\n```\n")
    if always_fail:
        body = "\n".join(row(n, c) for n, c in sorted(always_fail.items()))
        summary.write(f"### Always-fail\n```\n{body}\n```\n")

print(
    f"runs={runs} distinct_tests={len(seen)} "
    f"flaky={len(flaky)} always_fail={len(always_fail)}"
)
sys.exit(0)
