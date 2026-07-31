from __future__ import annotations

from src.product.store import (
    add_event,
    add_evidence,
    ensure_product_schema,
    load_events,
    load_evidence,
    load_translations,
    load_workspaces,
    upsert_translation,
    upsert_workspace,
)


def test_product_store_roundtrip(tmp_path) -> None:
    database = tmp_path / "product.db"
    ensure_product_schema(database)
    key = "abc"
    upsert_workspace(
        database,
        key,
        {
            "opportunity_url": "https://example.com/1",
            "opportunity_title": "Original title",
            "lifecycle_state": "test_planned",
            "buyer_hypothesis": "Operations manager",
            "smallest_test": "Manual service offer",
        },
    )
    add_evidence(
        database,
        key,
        evidence_type="interview",
        direction="supports",
        summary="Buyer confirmed the workflow problem",
    )
    add_event(
        database,
        key,
        event_type="price_test",
        outcome="Asked for a proposal",
        hours_spent=1.5,
    )
    upsert_translation(
        database,
        key,
        field_name="title",
        original_text="Original title",
        translated_text="Título traduzido",
    )

    workspaces = load_workspaces(database)
    evidence = load_evidence(database)
    events = load_events(database)
    translations = load_translations(database)

    assert workspaces.iloc[0]["buyer_hypothesis"] == "Operations manager"
    assert evidence.iloc[0]["direction"] == "supports"
    assert events.iloc[0]["event_type"] == "price_test"
    assert translations.iloc[0]["original_text"] == "Original title"
    assert translations.iloc[0]["translated_text"] == "Título traduzido"
    assert translations.iloc[0]["source_hash"]


def test_workspace_update_preserves_single_record(tmp_path) -> None:
    database = tmp_path / "product.db"
    upsert_workspace(database, "abc", {"lifecycle_state": "detected"})
    upsert_workspace(
        database,
        "abc",
        {"lifecycle_state": "under_review", "next_action": "Interview"},
    )
    workspaces = load_workspaces(database)
    assert len(workspaces) == 1
    assert workspaces.iloc[0]["lifecycle_state"] == "under_review"
    assert workspaces.iloc[0]["next_action"] == "Interview"
