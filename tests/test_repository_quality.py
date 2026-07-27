from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "README.md",
    "requirements-dev.txt",
    ".github/workflows/ci.yml",
    ".github/pull_request_template.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CHANGELOG.md",
    "docs/architecture.md",
    "docs/operations.md",
    "docs/project_state.md",
    "docs/decisions/0001-source-snapshot-runner-v2.md",
}


def test_professional_repository_files_exist() -> None:
    missing = sorted(
        relative
        for relative in REQUIRED_FILES
        if not (ROOT / relative).is_file()
    )
    assert missing == []


def test_readme_documents_runner_and_daily_command() -> None:
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "Runner V2" in content
    assert "python scripts/run_colab.py --mode all" in content
    assert "Stack Overflow" in content
    assert "DEV Community" in content


def test_ci_runs_compile_and_full_suite() -> None:
    content = (
        ROOT / ".github/workflows/ci.yml"
    ).read_text(encoding="utf-8")
    assert '"3.11"' in content
    assert '"3.12"' in content
    assert "python -m compileall -q src scripts tests" in content
    assert "python -m pytest -q" in content
    assert "requirements-dev.txt" in content


def test_project_state_preserves_roadmap_order() -> None:
    content = (
        ROOT / "docs/project_state.md"
    ).read_text(encoding="utf-8")
    positions = [
        content.index("Integrar novas fontes"),
        content.index("Unificar a operação do Colab"),
        content.index("Profissionalizar o repositório"),
        content.index("Ajustar a dashboard"),
    ]
    assert positions == sorted(positions)
    assert "6ec754e" in content


def test_no_sqlite_file_is_tracked() -> None:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    tracked = [
        line.strip()
        for line in completed.stdout.splitlines()
        if line.strip().lower().endswith(
            (".db", ".sqlite", ".sqlite3")
        )
    ]
    assert tracked == []


def test_documentation_does_not_contain_secret_values() -> None:
    paths = [
        ROOT / relative
        for relative in REQUIRED_FILES
        if relative.endswith((".md", ".yml"))
    ]
    forbidden = (
        "ghp_",
        "github_pat_",
        "x-access-token:",
        "Authorization: Bearer ",
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in paths
    )
    for marker in forbidden:
        assert marker not in combined
