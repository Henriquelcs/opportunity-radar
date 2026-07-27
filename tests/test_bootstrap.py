from __future__ import annotations

import subprocess
from pathlib import Path

from src.operations.bootstrap import ensure_repository_checkout


def test_zero_environment_bootstrap_clones_missing_repository(tmp_path) -> None:
    project = tmp_path / "opportunity-radar"
    calls: list[tuple[list[str], Path | None]] = []

    def fake_runner(command, cwd=None, check=False):
        calls.append((list(command), cwd))
        assert check is True
        if command[:2] == ["git", "clone"]:
            project.mkdir(parents=True)
            (project / ".git").mkdir()
        return subprocess.CompletedProcess(command, 0)

    result = ensure_repository_checkout(
        project,
        "https://github.com/example/opportunity-radar",
        runner=fake_runner,
    )

    assert result == project.resolve()
    assert calls[0][0][:4] == ["git", "clone", "--branch", "main"]
    assert project.joinpath(".git").exists()


def test_existing_environment_uses_fast_forward_update(tmp_path) -> None:
    project = tmp_path / "opportunity-radar"
    project.joinpath(".git").mkdir(parents=True)
    calls: list[list[str]] = []

    def fake_runner(command, cwd=None, check=False):
        calls.append(list(command))
        assert cwd == project.resolve()
        assert check is True
        return subprocess.CompletedProcess(command, 0)

    ensure_repository_checkout(
        project,
        "https://github.com/example/opportunity-radar",
        runner=fake_runner,
    )

    assert calls == [
        ["git", "fetch", "origin", "main"],
        ["git", "pull", "--ff-only", "origin", "main"],
    ]
