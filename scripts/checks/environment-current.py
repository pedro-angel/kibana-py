#!/usr/bin/env python3
"""Is the environment the gate is about to run in the one pyproject.toml declares?

The Definition-of-Done gate certifies a release. It has to certify the tree, not the
accident of what happens to be installed -- and a virtualenv created before a
dependency was added is not an environment this repository has ever tested. That drift
is invisible until some leaf fails on a missing import, three criteria deep, with an
error about a pytest flag rather than about the environment.

So: read the CURRENT ``[project.optional-dependencies]`` from pyproject.toml (the
source of truth, resolving the self-referential ``kibana-py[...]`` entries), and ask
the interpreter that will actually run the gate whether each one is installed. Missing
distributions are reported by name, with the one command that fixes them.

Deliberately NOT ``importlib.metadata.requires("kibana-py")``: that returns the
metadata recorded when the package was installed, so a stale editable install answers
with the stale extras and agrees with itself. The comparison only means something if
one side is the file on disk.

Stdlib only (tomllib is 3.11+, which `requires-python` already floors), and no network.

Usage:  environment-current.py [--extras dev,all] [--python /path/to/python]
Exit:   0 satisfied, 1 something is missing, 2 the script could not do its job.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PYPROJECT = REPO / "pyproject.toml"

#: A requirement string ("pytest>=7.0") down to its distribution name.
_NAME = re.compile(r"^\s*([A-Za-z0-9._-]+)")


def _normalize(name: str) -> str:
    """PEP 503 name normalization, so kibana_py and Kibana-PY are one name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _self_extras(req: str, project: str) -> list[str] | None:
    """The extras in a self-referential requirement (``kibana-py[docs,build]``)."""
    match = re.match(r"^([A-Za-z0-9._-]+)\[([^\]]+)\]$", req.strip())
    if match and _normalize(match.group(1)) == _normalize(project):
        return [extra.strip() for extra in match.group(2).split(",")]
    return None


def _resolve(extras: dict[str, list[str]], wanted: list[str], project: str) -> set[str]:
    """Flatten the named extras into distribution names, following self-references."""
    seen: set[str] = set()
    names: set[str] = set()
    stack = list(wanted)
    while stack:
        extra = stack.pop()
        if extra in seen:
            continue
        seen.add(extra)
        if extra not in extras:
            print(f"FAIL: pyproject.toml declares no '{extra}' extra", file=sys.stderr)
            raise SystemExit(2)
        for req in extras[extra]:
            self_ref = _self_extras(req, project)
            if self_ref is not None:
                stack.extend(self_ref)
                continue
            match = _NAME.match(req)
            if match:
                names.add(match.group(1))
    return names


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extras",
        default="dev,all",
        help="comma-separated extras to require (default: what `make setup` installs)",
    )
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="the interpreter to inspect (default: the one running this script)",
    )
    args = parser.parse_args()

    try:
        config = tomllib.loads(PYPROJECT.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"FAIL: cannot read {PYPROJECT}: {exc}", file=sys.stderr)
        return 2

    project_name = config.get("project", {}).get("name", "")
    if not project_name:
        print("FAIL: pyproject.toml declares no project name", file=sys.stderr)
        return 2
    extras = config.get("project", {}).get("optional-dependencies", {})
    if not extras:
        print("FAIL: pyproject.toml declares no optional-dependencies", file=sys.stderr)
        return 2

    required = _resolve(
        extras, [e.strip() for e in args.extras.split(",") if e.strip()], project_name
    )

    # Ask the target interpreter, which is generally NOT the one running this script.
    probe = (
        "import importlib.metadata as m, sys\n"
        "def found(name):\n"
        "    try:\n"
        "        m.version(name)\n"
        "        return True\n"
        "    except m.PackageNotFoundError:\n"
        "        return False\n"
        "print('\\n'.join(n for n in sys.argv[1:] if not found(n)))\n"
    )
    try:
        result = subprocess.run(
            [args.python, "-c", probe, *sorted(required)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"FAIL: cannot run {args.python}: {exc}", file=sys.stderr)
        return 2
    if result.returncode != 0:
        print(f"FAIL: {args.python} could not report its packages:", file=sys.stderr)
        print(result.stderr.strip(), file=sys.stderr)
        return 2

    missing = [line for line in result.stdout.split("\n") if line.strip()]
    if missing:
        print(
            f"NO-GO: {args.python} is missing "
            f"{len(missing)} declared dependency/ies:"
        )
        for name in missing:
            print(f"  - {name}")
        print("\nThe environment predates the current pyproject.toml. Refresh it:")
        print("  make setup")
        return 1

    print(f"GO: {len(required)} declared dependencies present ({args.extras})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
