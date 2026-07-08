import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import utils  # noqa: E402


def test_resource_prefix_strips_management_suffix():
    assert utils.resource_prefix("/x/lists_management.py") == "kbnpy-lists"
    assert utils.resource_prefix("/x/simple_status.py") == "kbnpy-simple-status"


def test_should_cleanup_no_tty_defaults_keep(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["ex.py"])  # no flags
    monkeypatch.setattr(sys.stdin, "isatty", lambda: False)
    assert utils.should_cleanup() is False


def test_should_cleanup_flags_win(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["ex.py", "--cleanup"])
    assert utils.should_cleanup() is True
    monkeypatch.setattr(sys, "argv", ["ex.py", "--no-cleanup"])
    assert utils.should_cleanup() is False


def test_print_kept_smoke(capsys):
    utils.print_kept([("list", "kbnpy-lists-bad-ips")])
    assert "kbnpy-lists-bad-ips" in capsys.readouterr().out
