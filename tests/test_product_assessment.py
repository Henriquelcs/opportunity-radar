from __future__ import annotations

import pandas as pd

from src.product.assessment import (
    assess_frame,
    opportunity_key,
    quality_metrics,
    select_next_opportunity,
)


def test_assessment_separates_discovery_from_business_validation() -> None:
    opportunities = pd.DataFrame(
        [
            {
                "title": "Automate manual spreadsheet support workflow with API",
                "url": "https://example.com/1",
                "source": "github",
                "score": 92,
                "pain_categories": "manual_work | support_load",
                "original_queries": "spreadsheet automation",
                "matched_queries": "spreadsheet automation tool",
                "match_count": 4,
                "curation_status": "valid",
                "curation_label": "Válida",
            }
        ]
    )
    assessed = assess_frame(opportunities)
    row = assessed.iloc[0]

    assert row["discovery_score"] == 92
    assert row["personal_fit_label"] in {"Alto", "Muito alto"}
    assert row["traceability_index"] == 100
    assert row["qualified"] == False
    assert row["priority_bucket"] == "Investigar comprador"
    assert "não mede mercado" in row["discovery_score_meaning"]


def test_qualification_requires_human_label_buyer_and_evidence() -> None:
    opportunity = pd.DataFrame(
        [
            {
                "title": "Webhook automation",
                "url": "https://example.com/2",
                "source": "stackoverflow",
                "score": 75,
                "pain_categories": "automation_demand",
                "original_queries": "customer support automation",
                "curation_status": "valid",
            }
        ]
    )
    key = opportunity_key("https://example.com/2")
    workspaces = pd.DataFrame(
        [
            {
                "opportunity_key": key,
                "lifecycle_state": "pain_confirmed",
                "buyer_hypothesis": "Gestor de suporte",
                "smallest_test": "Oferta manual",
            }
        ]
    )
    evidence = pd.DataFrame(
        [
            {
                "opportunity_key": key,
                "direction": "supports",
                "summary": "Entrevista confirmou retrabalho",
            }
        ]
    )
    assessed = assess_frame(opportunity, workspaces=workspaces, evidence=evidence)
    assert assessed.iloc[0]["qualified"] == True


def test_next_opportunity_excludes_false_positive() -> None:
    frame = pd.DataFrame(
        [
            {
                "title": "False",
                "url": "https://example.com/false",
                "curation_status": "false_positive",
                "lifecycle_state": "detected",
                "personal_fit_index": 90,
                "traceability_index": 100,
                "discovery_score": 99,
            },
            {
                "title": "Valid",
                "url": "https://example.com/valid",
                "curation_status": "valid",
                "lifecycle_state": "under_review",
                "personal_fit_index": 80,
                "traceability_index": 100,
                "discovery_score": 70,
            },
        ]
    )
    selected = select_next_opportunity(frame)
    assert selected.iloc[0]["url"] == "https://example.com/valid"


def test_quality_metrics_only_uses_labeled_items() -> None:
    frame = pd.DataFrame(
        [
            {"curation_status": "valid", "discovery_score": 90, "qualified": True},
            {"curation_status": "false_positive", "discovery_score": 80, "qualified": False},
            {"curation_status": "unreviewed", "discovery_score": 70, "qualified": False},
        ]
    )
    metrics = quality_metrics(frame)
    assert metrics["reviewed"] == 2
    assert metrics["precision"] == 0.5
    assert metrics["qualified"] == 1
