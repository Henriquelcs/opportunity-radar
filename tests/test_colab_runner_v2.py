from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_colab.py"
SPEC = importlib.util.spec_from_file_location("run_colab_v2", MODULE_PATH)
assert SPEC and SPEC.loader
run_colab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_colab)


def test_cloudflared_is_pinned_with_checksum() -> None:
    assert run_colab.CLOUDFLARED_VERSION == "2026.7.3"
    assert len(run_colab.CLOUDFLARED_SHA256) == 64
    assert "/2026.7.3/" in run_colab.CLOUDFLARED_URL


def test_long_running_commands_do_not_capture_output(monkeypatch) -> None:
    received = {}

    def fake_run(command, **kwargs):
        received.update(kwargs)

    monkeypatch.setattr(run_colab.subprocess, "run", fake_run)
    run_colab.run_command(["python", "-m", "pytest", "-q"])
    assert "capture_output" not in received
    assert received["check"] is True


def test_no_pkill_is_used() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    assert "pkill" not in source
    assert "capture_output=True" not in source


def test_project_root_is_added_for_direct_script_execution(monkeypatch, tmp_path) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    monkeypatch.setattr(run_colab.sys, "path", [str(scripts_dir)])

    run_colab.ensure_project_import_path(tmp_path)

    assert run_colab.sys.path[0] == str(tmp_path.resolve())


def test_cli_reports_full_unhandled_traceback(monkeypatch, capsys) -> None:
    def fail() -> int:
        raise RuntimeError("collect failed")

    monkeypatch.setattr(run_colab, "main", fail)

    assert run_colab.cli() == 1
    captured = capsys.readouterr()
    assert "[FATAL] RuntimeError: collect failed" in captured.err
    assert "Traceback (most recent call last)" in captured.err
