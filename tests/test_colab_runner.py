from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "run_colab.py"
SPEC = importlib.util.spec_from_file_location("run_colab", MODULE_PATH)
assert SPEC and SPEC.loader
run_colab = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(run_colab)


def test_default_queries_cover_three_pain_domains() -> None:
    assert run_colab.DEFAULT_QUERIES == (
        "repetitive data entry",
        "spreadsheet automation",
        "customer support automation",
    )


def test_extract_public_url_uses_trycloudflare_domain() -> None:
    log = (
        "INF Requesting new quick Tunnel\n"
        "https://clear-example.trycloudflare.com\n"
    )
    assert (
        run_colab.extract_public_url(log)
        == "https://clear-example.trycloudflare.com"
    )


def test_extract_public_url_returns_empty_when_absent() -> None:
    assert run_colab.extract_public_url("tunnel connected") == ""


def test_collection_command_contains_operational_arguments(
    tmp_path: Path,
) -> None:
    database = tmp_path / "radar.db"
    command = run_colab.build_collection_command(
        "manual data entry",
        database,
        limit=10,
        minimum_score=5,
        top=50,
        max_attempts=4,
        retry_delay_seconds=12,
        inter_query_delay_seconds=6,
    )

    assert "scripts/run_expanded_query.py" in command
    assert command[command.index("--query") + 1] == "manual data entry"
    assert command[command.index("--database") + 1] == str(database)
    assert command[command.index("--max-attempts") + 1] == "4"
