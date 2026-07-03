"""Nox automation for kibana-py project."""

import nox


@nox.session(python=["3.14"])
def test(session):
    """Run unit tests with pytest across all supported Python versions."""
    session.install(".[dev,all]")
    session.run("pytest", "tests/unit/", *session.posargs)


@nox.session
def format(session):
    """Format code with black and isort."""
    session.run("isort", "kibana/", "tests/", "examples/")
    session.run("black", "kibana/", "tests/", "examples/")


@nox.session
def lint(session):
    """Lint code with ruff and type check with mypy."""
    session.run("ruff", "check", "kibana/", "tests/")
    session.run("mypy", "kibana/")


@nox.session
def format_check(session):
    """Check code formatting without making changes."""
    session.run("isort", "--check-only", "kibana/", "tests/", "examples/")
    session.run("black", "--check", "kibana/", "tests/", "examples/")


@nox.session
def lint_fix(session):
    """Lint code with ruff and automatically fix issues."""
    session.run("ruff", "check", "--fix", "kibana/", "tests/")
