from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.dashboard.curation import (
    CURATION_LABELS,
    attach_curation,
    load_curation,
    save_curation,
)


def test_save_load_update_and_remove_curation(tmp_path: Path) -> None:
    database = tmp_path / "curation.db"
    url = "https://example.com/opportunity"

    save_curation(database, url, "review", "Validar disposição a pagar.")
    first = load_curation(database)

    assert len(first) == 1
    assert first.iloc[0]["status"] == "review"
    assert first.iloc[0]["notes"] == "Validar disposição a pagar."

    save_curation(database, url, "valid", "Dor recorrente confirmada.")
    updated = load_curation(database)

    assert len(updated) == 1
    assert updated.iloc[0]["status"] == "valid"
    assert updated.iloc[0]["notes"] == "Dor recorrente confirmada."

    save_curation(database, url, "unreviewed")
    assert load_curation(database).empty


def test_invalid_curation_is_rejected(tmp_path: Path) -> None:
    database = tmp_path / "curation.db"

    with pytest.raises(ValueError):
        save_curation(database, "", "valid")

    with pytest.raises(ValueError):
        save_curation(database, "https://example.com/1", "approved")


def test_attach_curation_defaults_and_saved_status() -> None:
    opportunities = pd.DataFrame(
        [
            {"url": "https://example.com/1", "title": "First"},
            {"url": "https://example.com/2", "title": "Second"},
        ]
    )
    curation = pd.DataFrame(
        [
            {
                "opportunity_url": "https://example.com/1",
                "status": "false_positive",
                "notes": "Produto pronto, não dor.",
                "updated_at": "2026-07-26T12:00:00+00:00",
            }
        ]
    )

    result = attach_curation(opportunities, curation)

    first = result[result["url"].eq("https://example.com/1")].iloc[0]
    second = result[result["url"].eq("https://example.com/2")].iloc[0]

    assert first["curation_label"] == CURATION_LABELS["false_positive"]
    assert first["curation_notes"] == "Produto pronto, não dor."
    assert second["curation_status"] == "unreviewed"
    assert second["curation_label"] == CURATION_LABELS["unreviewed"]
