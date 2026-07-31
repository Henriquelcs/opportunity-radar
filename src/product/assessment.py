from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from src.product.contracts import LIFECYCLE_LABELS, LIFECYCLE_ORDER


PROFILE_SKILL_SIGNALS: dict[str, tuple[str, ...]] = {
    "Automação de processos": (
        "automate",
        "automation",
        "manual",
        "manually",
        "repetitive",
        "workflow",
        "copy paste",
        "copy-paste",
        "spreadsheet",
        "excel",
        "form",
        "data entry",
        "too many clicks",
    ),
    "APIs e integrações": (
        "api",
        "webhook",
        "integration",
        "integrate",
        "sync",
        "connector",
        "rest",
    ),
    "Operações e suporte": (
        "support",
        "ticket",
        "customer service",
        "help desk",
        "helpdesk",
        "operations",
        "operational",
        "backoffice",
    ),
    "Dados e dashboards": (
        "dashboard",
        "report",
        "reporting",
        "sqlite",
        "database",
        "csv",
        "grafana",
        "metrics",
    ),
    "Python e ferramentas internas": (
        "python",
        "script",
        "streamlit",
        "bot",
        "internal tool",
        "google apps script",
        "apps script",
    ),
}

WORKSPACE_COMPLETENESS_FIELDS: tuple[str, ...] = (
    "problem_statement",
    "user_segment",
    "buyer_hypothesis",
    "solution_format",
    "acquisition_channel",
    "smallest_test",
    "price_test_hypothesis",
    "success_evidence",
    "discard_evidence",
    "next_action",
)

QUALIFICATION_STATES = {
    "pain_confirmed",
    "buyer_identified",
    "test_planned",
    "validating",
    "interest_confirmed",
    "price_tested",
    "mvp_approved",
    "building",
    "first_revenue",
    "scaling",
}

VALIDATION_STATES = {
    "test_planned",
    "validating",
    "interest_confirmed",
    "price_tested",
    "mvp_approved",
    "building",
    "first_revenue",
    "scaling",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def _numeric(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(number):
        return default
    return number


def _split_pipe(value: Any) -> list[str]:
    return [item.strip() for item in _text(value).split("|") if item.strip()]


def opportunity_key(
    url: Any,
    title: Any = "",
    source: Any = "",
) -> str:
    identity = _text(url) or "|".join(
        [_text(source).casefold(), _text(title).casefold()]
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _normalized_search_text(row: Mapping[str, Any]) -> str:
    values = (
        row.get("title", ""),
        row.get("pain_categories", ""),
        row.get("original_queries", ""),
        row.get("matched_queries", ""),
    )
    return re.sub(
        r"\s+",
        " ",
        " ".join(_text(value) for value in values).casefold(),
    ).strip()


def personal_fit_signals(row: Mapping[str, Any]) -> list[str]:
    text = _normalized_search_text(row)
    matches: list[str] = []
    for skill, patterns in PROFILE_SKILL_SIGNALS.items():
        if any(pattern in text for pattern in patterns):
            matches.append(skill)
    return matches


def personal_fit_band(signals: Iterable[str]) -> tuple[str, int]:
    count = len(list(signals))
    if count >= 4:
        return "Muito alto", 90
    if count == 3:
        return "Alto", 80
    if count == 2:
        return "Médio", 65
    if count == 1:
        return "Baixo", 45
    return "Não demonstrado", 20


def evidence_traceability(row: Mapping[str, Any]) -> tuple[int, list[str]]:
    checks = {
        "fonte pública": bool(_text(row.get("source"))),
        "URL original": bool(_text(row.get("url"))),
        "título original": bool(_text(row.get("title"))),
        "sinal de dor detectado": bool(_text(row.get("pain_categories"))),
        "consulta rastreável": bool(_text(row.get("original_queries"))),
    }
    present = [label for label, ok in checks.items() if ok]
    return int(round(100 * len(present) / len(checks))), present


def workspace_completeness(workspace: Mapping[str, Any]) -> tuple[int, list[str]]:
    completed = [
        field
        for field in WORKSPACE_COMPLETENESS_FIELDS
        if _text(workspace.get(field))
        and _text(workspace.get(field)).casefold() not in {"não definido", "nao definido"}
    ]
    return int(round(100 * len(completed) / len(WORKSPACE_COMPLETENESS_FIELDS))), completed


def _lifecycle_rank(state: str) -> int:
    try:
        return LIFECYCLE_ORDER.index(state)
    except ValueError:
        return 0


def assess_opportunity(
    row: Mapping[str, Any],
    *,
    workspace: Mapping[str, Any] | None = None,
    evidence: pd.DataFrame | None = None,
    events: pd.DataFrame | None = None,
) -> dict[str, Any]:
    workspace = workspace or {}
    key = opportunity_key(row.get("url"), row.get("title"), row.get("source"))
    lifecycle_state = _text(workspace.get("lifecycle_state")) or "detected"
    if lifecycle_state not in LIFECYCLE_LABELS:
        lifecycle_state = "detected"

    curation_status = _text(row.get("curation_status")) or "unreviewed"
    fit_signals = personal_fit_signals(row)
    fit_label, fit_index = personal_fit_band(fit_signals)
    traceability_index, traceability_items = evidence_traceability(row)
    readiness_index, completed_fields = workspace_completeness(workspace)

    opportunity_evidence = pd.DataFrame() if evidence is None else evidence.copy()
    if not opportunity_evidence.empty and "opportunity_key" in opportunity_evidence:
        opportunity_evidence = opportunity_evidence[
            opportunity_evidence["opportunity_key"].astype(str).eq(key)
        ]
    opportunity_events = pd.DataFrame() if events is None else events.copy()
    if not opportunity_events.empty and "opportunity_key" in opportunity_events:
        opportunity_events = opportunity_events[
            opportunity_events["opportunity_key"].astype(str).eq(key)
        ]

    supporting_evidence = 0
    contradicting_evidence = 0
    if not opportunity_evidence.empty and "direction" in opportunity_evidence:
        directions = opportunity_evidence["direction"].astype(str)
        supporting_evidence = int(directions.eq("supports").sum())
        contradicting_evidence = int(directions.eq("contradicts").sum())

    event_types: set[str] = set()
    if not opportunity_events.empty and "event_type" in opportunity_events:
        event_types = set(opportunity_events["event_type"].astype(str))
    revenue_amount = 0.0
    if not opportunity_events.empty and "amount_brl" in opportunity_events:
        revenue_rows = opportunity_events[
            opportunity_events.get("event_type", "").astype(str).eq("revenue")
        ]
        revenue_amount = float(
            pd.to_numeric(revenue_rows["amount_brl"], errors="coerce").fillna(0).sum()
        )

    buyer_identified = bool(_text(workspace.get("buyer_hypothesis")))
    smallest_test_defined = bool(_text(workspace.get("smallest_test")))
    human_validated = curation_status == "valid"
    qualified = (
        human_validated
        and lifecycle_state in QUALIFICATION_STATES
        and buyer_identified
        and supporting_evidence > 0
    )

    if curation_status == "false_positive" or lifecycle_state == "discarded":
        priority_bucket = "Descartar"
        recommended_action = "Preservar o motivo do descarte para calibrar o radar."
    elif revenue_amount > 0 or lifecycle_state == "first_revenue":
        priority_bucket = "Receita registrada"
        recommended_action = "Registrar custo, horas, aprendizado e decidir continuidade."
    elif not buyer_identified:
        priority_bucket = "Investigar comprador"
        recommended_action = "Identificar quem sofre a dor e quem controla o orçamento."
    elif supporting_evidence == 0:
        priority_bucket = "Buscar evidência"
        recommended_action = "Obter uma evidência independente antes de construir."
    elif not smallest_test_defined:
        priority_bucket = "Definir menor teste"
        recommended_action = "Planejar um teste comercial menor que o produto."
    elif "price_test" not in event_types:
        priority_bucket = "Testar interesse e preço"
        recommended_action = "Apresentar uma oferta concreta e registrar a resposta."
    elif lifecycle_state in VALIDATION_STATES:
        priority_bucket = "Em validação"
        recommended_action = _text(workspace.get("next_action")) or "Executar o próximo passo registrado."
    else:
        priority_bucket = "Analisar agora"
        recommended_action = _text(workspace.get("next_action")) or "Revisar evidência, comprador e menor teste."

    return {
        "opportunity_key": key,
        "discovery_score": _numeric(row.get("score"), default=0.0),
        "discovery_score_meaning": "Força heurística do sinal público; não mede mercado ou receita.",
        "traceability_index": traceability_index,
        "traceability_items": " | ".join(traceability_items),
        "personal_fit_index": fit_index,
        "personal_fit_label": fit_label,
        "personal_fit_signals": " | ".join(fit_signals),
        "validation_readiness_index": readiness_index,
        "completed_workspace_fields": len(completed_fields),
        "supporting_evidence": supporting_evidence,
        "contradicting_evidence": contradicting_evidence,
        "validation_events": len(opportunity_events),
        "revenue_brl": revenue_amount,
        "lifecycle_state": lifecycle_state,
        "lifecycle_label": LIFECYCLE_LABELS[lifecycle_state],
        "priority_bucket": priority_bucket,
        "recommended_action": recommended_action,
        "buyer_identified": buyer_identified,
        "smallest_test_defined": smallest_test_defined,
        "human_validated": human_validated,
        "qualified": qualified,
        "lifecycle_rank": _lifecycle_rank(lifecycle_state),
    }


def assess_frame(
    opportunities: pd.DataFrame,
    *,
    workspaces: pd.DataFrame | None = None,
    evidence: pd.DataFrame | None = None,
    events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if opportunities.empty:
        return opportunities.copy()

    workspace_by_key: dict[str, dict[str, Any]] = {}
    if workspaces is not None and not workspaces.empty:
        workspace_by_key = {
            str(row["opportunity_key"]): row.to_dict()
            for _, row in workspaces.iterrows()
            if _text(row.get("opportunity_key"))
        }

    records: list[dict[str, Any]] = []
    for _, row in opportunities.iterrows():
        base = row.to_dict()
        key = opportunity_key(base.get("url"), base.get("title"), base.get("source"))
        assessment = assess_opportunity(
            base,
            workspace=workspace_by_key.get(key, {}),
            evidence=evidence,
            events=events,
        )
        records.append({**base, **assessment})
    return pd.DataFrame(records)


def select_next_opportunity(assessed: pd.DataFrame) -> pd.DataFrame:
    if assessed.empty:
        return assessed.copy()
    frame = assessed.copy()
    if "curation_status" in frame:
        frame = frame[
            ~frame["curation_status"].astype(str).isin({"false_positive"})
        ]
    if "lifecycle_state" in frame:
        frame = frame[
            ~frame["lifecycle_state"].astype(str).isin({"discarded"})
        ]
    if frame.empty:
        return frame

    curation_priority = {
        "valid": 3,
        "review": 2,
        "unreviewed": 1,
        "": 1,
    }
    frame["_curation_priority"] = (
        frame.get("curation_status", "")
        .astype(str)
        .map(curation_priority)
        .fillna(0)
    )
    frame["_fit"] = pd.to_numeric(
        frame.get("personal_fit_index", 0), errors="coerce"
    ).fillna(0)
    frame["_traceability"] = pd.to_numeric(
        frame.get("traceability_index", 0), errors="coerce"
    ).fillna(0)
    frame["_discovery"] = pd.to_numeric(
        frame.get("discovery_score", frame.get("score", 0)), errors="coerce"
    ).fillna(0)
    match_series = (
        frame["match_count"]
        if "match_count" in frame
        else pd.Series(0, index=frame.index, dtype=float)
    )
    frame["_matches"] = pd.to_numeric(match_series, errors="coerce").fillna(0)
    frame = frame.sort_values(
        ["_curation_priority", "_fit", "_traceability", "_discovery", "_matches"],
        ascending=False,
    )
    return frame.drop(
        columns=["_curation_priority", "_fit", "_traceability", "_discovery", "_matches"]
    ).head(1)


def quality_metrics(assessed: pd.DataFrame, *, k: int = 10) -> dict[str, Any]:
    if assessed.empty:
        return {
            "signals": 0,
            "reviewed": 0,
            "valid": 0,
            "false_positive": 0,
            "precision": None,
            "precision_at_k": None,
            "qualified": 0,
        }
    statuses = assessed.get(
        "curation_status", pd.Series(["unreviewed"] * len(assessed), index=assessed.index)
    ).astype(str)
    labeled_mask = statuses.isin({"valid", "false_positive"})
    reviewed = int(labeled_mask.sum())
    valid = int(statuses.eq("valid").sum())
    false_positive = int(statuses.eq("false_positive").sum())
    precision = valid / reviewed if reviewed else None

    ranked = assessed.assign(
        _score=pd.to_numeric(
            assessed.get("discovery_score", assessed.get("score", 0)), errors="coerce"
        ).fillna(0)
    ).sort_values("_score", ascending=False).head(k)
    ranked_statuses = ranked.get(
        "curation_status", pd.Series(["unreviewed"] * len(ranked), index=ranked.index)
    ).astype(str)
    ranked_labeled = ranked_statuses.isin({"valid", "false_positive"})
    precision_at_k = (
        float(ranked_statuses[ranked_labeled].eq("valid").mean())
        if ranked_labeled.any()
        else None
    )
    return {
        "signals": len(assessed),
        "reviewed": reviewed,
        "valid": valid,
        "false_positive": false_positive,
        "precision": precision,
        "precision_at_k": precision_at_k,
        "qualified": int(assessed.get("qualified", False).astype(bool).sum()),
    }
