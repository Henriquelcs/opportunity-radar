from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Sequence


CommandRunner = Callable[..., subprocess.CompletedProcess]


def ensure_repository_checkout(
    project_dir: str | Path,
    repository_url: str,
    *,
    branch: str = "main",
    runner: CommandRunner = subprocess.run,
) -> Path:
    """Clona em ambiente zerado ou atualiza checkout existente via fast-forward."""
    target = Path(project_dir).expanduser().resolve()
    git_dir = target / ".git"
    if not git_dir.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        runner(
            [
                "git",
                "clone",
                "--branch",
                branch,
                "--single-branch",
                repository_url,
                str(target),
            ],
            check=True,
        )
        return target

    runner(
        ["git", "fetch", "origin", branch],
        cwd=target,
        check=True,
    )
    runner(
        ["git", "pull", "--ff-only", "origin", branch],
        cwd=target,
        check=True,
    )
    return target
