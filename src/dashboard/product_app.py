from __future__ import annotations

import hashlib
import html
import os
import re
import sys
from pathlib import Path
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.dashboard.curation import (
    CURATION_LABELS,
    LABEL_TO_STATUS,
    attach_curation,
    ensure_curation_schema,
    load_curation,
    save_curation,
)
from src.dashboard.data_access import discover_databases, load_radar_data
from src.dashboard.presentation import build_landing_summary, source_status_overview
from src.product.assessment import (
    assess_frame,
    opportunity_key,
    quality_metrics,
    select_next_opportunity,
)
from src.product.contracts import (
    EVIDENCE_DIRECTIONS,
    EVIDENCE_TYPES,
    EVENT_TYPES,
    LIFECYCLE_LABELS,
    LIFECYCLE_ORDER,
    OFFICIAL_PRODUCT_DEFINITION,
    SOLUTION_FORMATS,
)
from src.product.store import (
    PRODUCT_DATABASE_NAME,
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


DATA_DIR = Path(
    os.getenv("OPPORTUNITY_RADAR_DATA_DIR", str(PROJECT_DIR / "data"))
).resolve()
CURATION_DB = DATA_DIR / "opportunity_radar_curation.db"
PRODUCT_DB = DATA_DIR / PRODUCT_DATABASE_NAME


CSS = """
<style>
:root {
    --radar-accent: #63e6be;
    --radar-blue: #74a7ff;
    --radar-purple: #a78bfa;
    --radar-warning: #f7c66f;
    --radar-danger: #ff8c8c;
    --radar-muted: #93a0b4;
    --radar-border: rgba(148, 163, 184, .20);
    --radar-surface: rgba(15, 23, 42, .54);
}
.block-container {max-width: 1420px; padding-top: 1rem; padding-bottom: 4rem;}
[data-testid="stSidebar"] {border-right: 1px solid var(--radar-border);}
[data-testid="stMetric"] {
    border: 1px solid var(--radar-border); border-radius: 18px;
    padding: 15px 17px; min-height: 112px;
    background: linear-gradient(145deg, rgba(99,230,190,.06), rgba(116,167,255,.025));
}
.radar-hero {
    position: relative; overflow: hidden; border-radius: 30px;
    border: 1px solid rgba(99,230,190,.26);
    padding: clamp(1.7rem, 4vw, 3.5rem); margin-bottom: 1rem;
    background:
      radial-gradient(circle at 85% 12%, rgba(116,167,255,.20), transparent 32%),
      radial-gradient(circle at 8% 90%, rgba(99,230,190,.16), transparent 35%),
      linear-gradient(135deg, #0f172a 0%, #07101e 100%);
    box-shadow: 0 24px 70px rgba(0,0,0,.24);
}
.radar-hero h1 {margin:0; color:#f8fafc; font-size:clamp(2.2rem,5vw,4.35rem); line-height:1.02; letter-spacing:-.055em; max-width:960px;}
.radar-hero h1 span {color:var(--radar-accent);}
.radar-hero p {max-width:830px; color:#bdc8d8; line-height:1.65; font-size:clamp(1rem,1.4vw,1.16rem); margin:1.1rem 0 1.2rem;}
.kicker {color:var(--radar-accent); text-transform:uppercase; letter-spacing:.12em; font-size:.76rem; font-weight:800; margin-bottom:.75rem;}
.chip {display:inline-flex; margin:.2rem .35rem .2rem 0; padding:.42rem .68rem; border-radius:999px; border:1px solid var(--radar-border); color:#cbd5e1; font-size:.78rem; font-weight:700; background:rgba(255,255,255,.035);}
.chip-green {color:#79e7bd; border-color:rgba(34,197,94,.26); background:rgba(34,197,94,.09);}
.chip-yellow {color:#f7c66f; border-color:rgba(245,158,11,.26); background:rgba(245,158,11,.09);}
.chip-red {color:#ff9b9b; border-color:rgba(239,68,68,.26); background:rgba(239,68,68,.09);}
.section-title {font-size:clamp(1.55rem,2.4vw,2.05rem); letter-spacing:-.035em; margin:2.1rem 0 .3rem; font-weight:800;}
.section-copy {color:var(--radar-muted); max-width:900px; margin-bottom:1rem;}
.decision-card {border:1px solid rgba(99,230,190,.24); border-radius:24px; padding:1.25rem 1.35rem; background:linear-gradient(145deg,rgba(99,230,190,.065),rgba(116,167,255,.035));}
.decision-card h3 {font-size:1.45rem; letter-spacing:-.025em; margin:.45rem 0 .65rem;}
.fact-grid {display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:.75rem; margin:.85rem 0;}
.fact-card {border:1px solid var(--radar-border); border-radius:16px; padding:.85rem; background:rgba(148,163,184,.035);}
.fact-card strong {display:block; margin-bottom:.32rem;}
.fact-card span {color:var(--radar-muted); font-size:.86rem; line-height:1.45;}
.knowledge {border-left:4px solid var(--radar-blue); padding:.7rem .85rem; margin:.55rem 0; background:rgba(116,167,255,.055); border-radius:0 12px 12px 0;}
.knowledge.evidence {border-color:var(--radar-accent); background:rgba(99,230,190,.055);}
.knowledge.inference {border-color:var(--radar-purple); background:rgba(167,139,250,.055);}
.knowledge.hypothesis {border-color:var(--radar-warning); background:rgba(245,158,11,.055);}
.knowledge.decision {border-color:#fb7185; background:rgba(251,113,133,.055);}
.knowledge b {font-size:.8rem; text-transform:uppercase; letter-spacing:.07em;}
.knowledge div {color:#c5cfdd; margin-top:.2rem; line-height:1.5;}
.lifecycle {display:flex; overflow-x:auto; gap:.55rem; padding:.4rem 0 .8rem;}
.lifecycle-step {min-width:145px; border:1px solid var(--radar-border); border-radius:14px; padding:.7rem; color:var(--radar-muted); font-size:.78rem; background:rgba(148,163,184,.03);}
.lifecycle-step.active {color:#08111d; background:var(--radar-accent); border-color:var(--radar-accent); font-weight:800;}
.lifecycle-step.done {color:#9cebd5; border-color:rgba(99,230,190,.35); background:rgba(99,230,190,.07);}
.score-note {border:1px solid rgba(245,158,11,.25); background:rgba(245,158,11,.055); border-radius:15px; padding:.85rem 1rem; color:#d8cba9;}
.small-muted {color:var(--radar-muted); font-size:.86rem;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:18px; border-color:var(--radar-border);}
div[data-testid="stDataFrame"] {border:1px solid rgba(148,163,184,.12); border-radius:14px; overflow:hidden;}
@media (max-width:760px) {.radar-hero{border-radius:22px;padding:1.45rem}.radar-hero h1{font-size:2.25rem}}
</style>
"""


@st.cache_data(ttl=20, show_spinner=False)
def cached_radar_data(data_dir: str, selected_files: tuple[str, ...]):
    return load_radar_data(data_dir, selected_files)


@st.cache_data(ttl=5, show_spinner=False)
def cached_curation(database_path: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    return load_curation(database_path)


@st.cache_data(ttl=5, show_spinner=False)
def cached_product_data(database_path: str, modified_ns: int):
    del modified_ns
    return (
        load_workspaces(database_path),
        load_evidence(database_path),
        load_events(database_path),
        load_translations(database_path),
    )


def _text(value: Any, fallback: str = "") -> str:
    if value is None:
        return fallback
    try:
        if pd.isna(value):
            return fallback
    except (TypeError, ValueError):
        pass
    result = str(value).strip()
    return result or fallback


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return default if pd.isna(result) else result


def _unique_nonempty(series: pd.Series) -> list[str]:
    return sorted(
        {_text(value) for value in series if _text(value)},
        key=str.casefold,
    )


def _consolidate(opportunities: pd.DataFrame) -> pd.DataFrame:
    if opportunities.empty:
        return opportunities.copy()
    frame = opportunities.copy()
    frame["_score"] = pd.to_numeric(frame.get("score", 0), errors="coerce").fillna(0)
    frame["_matches"] = pd.to_numeric(frame.get("match_count", 0), errors="coerce").fillna(0)
    frame = frame.sort_values(["_score", "_matches"], ascending=False)
    url_key = frame.get("url", pd.Series("", index=frame.index)).astype(str).str.strip()
    title_key = (
        frame.get("title", pd.Series("", index=frame.index))
        .astype(str)
        .str.casefold()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
    frame["_key"] = url_key.mask(url_key.eq(""), title_key)
    return frame.drop_duplicates("_key").drop(columns=["_score", "_matches", "_key"])


def _format_percent(value: float | None) -> str:
    return "Sem baseline" if value is None else f"{value * 100:.1f}%"


def _workspace_for(workspaces: pd.DataFrame, key: str) -> dict[str, Any]:
    if workspaces.empty or "opportunity_key" not in workspaces:
        return {}
    rows = workspaces[workspaces["opportunity_key"].astype(str).eq(key)]
    return {} if rows.empty else rows.iloc[0].to_dict()


def _translation_for(
    translations: pd.DataFrame,
    key: str,
    field_name: str,
) -> dict[str, Any]:
    if translations.empty:
        return {}
    rows = translations[
        translations["opportunity_key"].astype(str).eq(key)
        & translations["field_name"].astype(str).eq(field_name)
    ]
    return {} if rows.empty else rows.iloc[0].to_dict()


def _render_knowledge_block(kind: str, label: str, content: str) -> None:
    safe_label = html.escape(label)
    safe_content = html.escape(content or "Não registrado")
    st.markdown(
        f'<div class="knowledge {kind}"><b>{safe_label}</b><div>{safe_content}</div></div>',
        unsafe_allow_html=True,
    )


def _render_lifecycle(current_state: str) -> None:
    current_index = LIFECYCLE_ORDER.index(current_state) if current_state in LIFECYCLE_ORDER else 0
    blocks: list[str] = []
    for index, state in enumerate(LIFECYCLE_ORDER):
        css = "active" if index == current_index else "done" if index < current_index else ""
        blocks.append(
            f'<div class="lifecycle-step {css}">{index + 1}. {html.escape(LIFECYCLE_LABELS[state])}</div>'
        )
    st.markdown('<div class="lifecycle">' + "".join(blocks) + "</div>", unsafe_allow_html=True)


def _render_opportunity_table(frame: pd.DataFrame, height: int = 520) -> None:
    if frame.empty:
        st.info("Nenhum sinal disponível para os filtros selecionados.")
        return
    columns = [
        column
        for column in (
            "title",
            "source",
            "discovery_score",
            "personal_fit_label",
            "traceability_index",
            "lifecycle_label",
            "priority_bucket",
            "curation_label",
            "url",
        )
        if column in frame.columns
    ]
    display = frame[columns].copy()
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=height,
        column_config={
            "title": st.column_config.TextColumn("Sinal", width="large"),
            "source": st.column_config.TextColumn("Fonte", width="small"),
            "discovery_score": st.column_config.NumberColumn("Score de descoberta", format="%.1f"),
            "personal_fit_label": st.column_config.TextColumn("Aderência ao Henrique"),
            "traceability_index": st.column_config.ProgressColumn("Rastreabilidade", min_value=0, max_value=100, format="%d%%"),
            "lifecycle_label": st.column_config.TextColumn("Etapa"),
            "priority_bucket": st.column_config.TextColumn("Próxima decisão", width="medium"),
            "curation_label": st.column_config.TextColumn("Curadoria"),
            "url": st.column_config.LinkColumn("Original", display_text="Abrir"),
        },
    )


def _render_source_health(source_sync_runs: pd.DataFrame) -> None:
    overview = source_status_overview(source_sync_runs)
    if overview.empty:
        st.info("Nenhum estado de fonte disponível.")
    else:
        st.dataframe(overview, use_container_width=True, hide_index=True)


def _selected_row(frame: pd.DataFrame, key_prefix: str) -> pd.Series | None:
    if frame.empty:
        st.info("Nenhum sinal disponível.")
        return None
    options = frame["opportunity_key"].astype(str).tolist()
    title_by_key = {
        str(row["opportunity_key"]): f"{_text(row.get('title'), 'Sem título')} · {_text(row.get('source'), 'fonte')}"
        for _, row in frame.iterrows()
    }
    preferred = _text(st.session_state.get("selected_opportunity_key"))
    index = options.index(preferred) if preferred in options else 0
    selected = st.selectbox(
        "Selecione o sinal",
        options=options,
        index=index,
        format_func=lambda value: title_by_key.get(value, value),
        key=f"{key_prefix}_opportunity_selector",
    )
    st.session_state["selected_opportunity_key"] = selected
    return frame[frame["opportunity_key"].astype(str).eq(selected)].iloc[0]


def _workspace_form(row: pd.Series, workspace: dict[str, Any]) -> None:
    key = str(row["opportunity_key"])
    state = _text(workspace.get("lifecycle_state"), "detected")
    if state not in LIFECYCLE_LABELS:
        state = "detected"

    st.markdown("### Contrato de validação")
    st.caption("Campos vazios permanecem desconhecidos. Nenhum custo, prazo, comprador ou faturamento é inventado.")
    with st.form(f"workspace_form_{key}"):
        left, right = st.columns(2)
        with left:
            lifecycle_state = st.selectbox(
                "Etapa do ciclo de vida",
                options=list(LIFECYCLE_ORDER),
                index=list(LIFECYCLE_ORDER).index(state),
                format_func=lambda value: LIFECYCLE_LABELS[value],
            )
            problem_statement = st.text_area(
                "Problema em uma frase",
                value=_text(workspace.get("problem_statement")),
                placeholder="Quem enfrenta qual problema, em qual contexto?",
            )
            user_segment = st.text_input(
                "Usuário afetado",
                value=_text(workspace.get("user_segment")),
                placeholder="Ainda não identificado",
            )
            buyer_hypothesis = st.text_input(
                "Possível comprador — hipótese",
                value=_text(workspace.get("buyer_hypothesis")),
                placeholder="Não confundir usuário com comprador",
            )
            current_format = _text(workspace.get("solution_format"), "Não definido")
            if current_format not in SOLUTION_FORMATS:
                current_format = "Não definido"
            solution_format = st.selectbox(
                "Formato inicial da solução",
                options=list(SOLUTION_FORMATS),
                index=list(SOLUTION_FORMATS).index(current_format),
            )
            monetization_hypothesis = st.text_area(
                "Hipótese de monetização",
                value=_text(workspace.get("monetization_hypothesis")),
                placeholder="Ex.: serviço por entrega. Ainda é hipótese.",
            )
        with right:
            acquisition_channel = st.text_input(
                "Primeiro canal de acesso",
                value=_text(workspace.get("acquisition_channel")),
                placeholder="Como Henrique chegará ao possível comprador?",
            )
            smallest_test = st.text_area(
                "Menor teste antes de construir",
                value=_text(workspace.get("smallest_test")),
                placeholder="Oferta, conversa, demonstração ou execução manual.",
            )
            price_test_hypothesis = st.text_input(
                "Preço a testar — hipótese",
                value=_text(workspace.get("price_test_hypothesis")),
                placeholder="Deixar vazio até existir uma premissa defensável",
            )
            success_evidence = st.text_area(
                "Evidência necessária para continuar",
                value=_text(workspace.get("success_evidence")),
                placeholder="Comportamento observável, não opinião vaga.",
            )
            discard_evidence = st.text_area(
                "Evidência para pausar ou descartar",
                value=_text(workspace.get("discard_evidence")),
                placeholder="Defina antes de se apegar à ideia.",
            )
            next_action = st.text_input(
                "Próximo passo concreto",
                value=_text(workspace.get("next_action")),
                placeholder="Uma ação pequena e executável",
            )
        limits = st.columns(3)
        budget_limit = limits[0].text_input(
            "Limite de orçamento",
            value=_text(workspace.get("budget_limit")),
            placeholder="Não definido",
        )
        weekly_hours_limit = limits[1].text_input(
            "Horas semanais disponíveis",
            value=_text(workspace.get("weekly_hours_limit")),
            placeholder="Não definido",
        )
        target_validation_date = limits[2].text_input(
            "Data-alvo da decisão",
            value=_text(workspace.get("target_validation_date")),
            placeholder="AAAA-MM-DD",
        )
        notes = st.text_area("Notas", value=_text(workspace.get("notes")))
        submitted = st.form_submit_button("Salvar plano de validação", type="primary", use_container_width=True)

    if submitted:
        upsert_workspace(
            PRODUCT_DB,
            key,
            {
                "opportunity_url": _text(row.get("url")),
                "opportunity_title": _text(row.get("title")),
                "lifecycle_state": lifecycle_state,
                "problem_statement": problem_statement,
                "user_segment": user_segment,
                "buyer_hypothesis": buyer_hypothesis,
                "solution_format": solution_format,
                "monetization_hypothesis": monetization_hypothesis,
                "acquisition_channel": acquisition_channel,
                "smallest_test": smallest_test,
                "price_test_hypothesis": price_test_hypothesis,
                "success_evidence": success_evidence,
                "discard_evidence": discard_evidence,
                "budget_limit": budget_limit,
                "weekly_hours_limit": weekly_hours_limit,
                "target_validation_date": target_validation_date,
                "next_action": next_action,
                "notes": notes,
            },
        )
        st.cache_data.clear()
        st.toast("Plano de validação salvo.", icon="✅")
        st.rerun()


def _translation_form(row: pd.Series, translations: pd.DataFrame) -> None:
    key = str(row["opportunity_key"])
    original = _text(row.get("title"))
    translation = _translation_for(translations, key, "title")
    st.markdown("### Original e tradução")
    st.caption("O original é imutável. Tradução é uma camada separada, versionada pelo hash do conteúdo.")
    mode = st.radio("Exibição", ["Original", "Tradução"], horizontal=True, key=f"translation_mode_{key}")
    if mode == "Tradução" and _text(translation.get("translated_text")):
        st.info(_text(translation.get("translated_text")))
    else:
        st.info(original or "Título original indisponível")
    with st.form(f"translation_form_{key}"):
        translated = st.text_area(
            "Tradução para português",
            value=_text(translation.get("translated_text")),
            placeholder="Tradução manual nesta fase; URLs, IDs e código não devem ser alterados.",
        )
        save_translation = st.form_submit_button("Salvar tradução", use_container_width=True)
    if save_translation:
        upsert_translation(
            PRODUCT_DB,
            key,
            field_name="title",
            original_text=original,
            translated_text=translated,
            provider="manual",
        )
        st.cache_data.clear()
        st.toast("Tradução salva sem alterar o original.", icon="🌐")
        st.rerun()


def _evidence_and_event_forms(row: pd.Series) -> None:
    key = str(row["opportunity_key"])
    left, right = st.columns(2)
    with left:
        st.markdown("### Registrar evidência")
        with st.form(f"evidence_form_{key}"):
            evidence_type = st.selectbox(
                "Tipo",
                options=list(EVIDENCE_TYPES),
                format_func=lambda value: EVIDENCE_TYPES[value],
            )
            direction = st.selectbox(
                "Direção",
                options=list(EVIDENCE_DIRECTIONS),
                format_func=lambda value: EVIDENCE_DIRECTIONS[value],
            )
            summary = st.text_area("O que foi observado?", placeholder="Descreva o fato observável.")
            source_url = st.text_input("Fonte ou referência", placeholder="URL opcional")
            raw_excerpt = st.text_area("Trecho original", placeholder="Preserve o conteúdo literal quando necessário.")
            occurred_at = st.text_input("Data da evidência", placeholder="AAAA-MM-DD")
            save_evidence = st.form_submit_button("Salvar evidência", use_container_width=True)
        if save_evidence:
            add_evidence(
                PRODUCT_DB,
                key,
                evidence_type=evidence_type,
                direction=direction,
                summary=summary,
                source_url=source_url,
                raw_excerpt=raw_excerpt,
                occurred_at=occurred_at,
            )
            st.cache_data.clear()
            st.toast("Evidência registrada.", icon="🧾")
            st.rerun()

    with right:
        st.markdown("### Registrar ação ou resultado")
        with st.form(f"event_form_{key}"):
            event_type = st.selectbox(
                "Evento",
                options=list(EVENT_TYPES),
                format_func=lambda value: EVENT_TYPES[value],
            )
            outcome = st.text_area("Resultado observado", placeholder="Resposta, decisão ou resultado real.")
            numeric = st.columns(3)
            amount_brl = numeric[0].number_input("Receita (R$)", min_value=0.0, value=0.0, step=10.0)
            hours_spent = numeric[1].number_input("Horas", min_value=0.0, value=0.0, step=0.5)
            cost_brl = numeric[2].number_input("Custo (R$)", min_value=0.0, value=0.0, step=10.0)
            event_notes = st.text_area("Notas do evento")
            event_date = st.text_input("Data do evento", placeholder="AAAA-MM-DD")
            save_event = st.form_submit_button("Salvar evento", use_container_width=True)
        if save_event:
            add_event(
                PRODUCT_DB,
                key,
                event_type=event_type,
                outcome=outcome,
                amount_brl=amount_brl if amount_brl > 0 else None,
                hours_spent=hours_spent if hours_spent > 0 else None,
                cost_brl=cost_brl if cost_brl > 0 else None,
                notes=event_notes,
                occurred_at=event_date,
            )
            st.cache_data.clear()
            st.toast("Evento registrado.", icon="📌")
            st.rerun()


def _render_decision_card(row: pd.Series, *, widget_scope: str) -> None:
    opportunity_key = _text(row.get("opportunity_key"), "unknown")
    title = html.escape(_text(row.get("title"), "Sinal sem título"))
    source = html.escape(_text(row.get("source"), "Fonte não informada"))
    action = html.escape(_text(row.get("recommended_action"), "Analisar"))
    bucket = html.escape(_text(row.get("priority_bucket"), "Analisar"))
    st.markdown(
        f"""
        <div class="decision-card">
          <span class="chip chip-green">{source}</span>
          <span class="chip">{bucket}</span>
          <h3>{title}</h3>
          <div class="small-muted"><b>Próximo passo recomendado:</b> {action}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(4)
    cols[0].metric("Score de descoberta", f"{_number(row.get('discovery_score')):.1f}", help="Heurística do sinal. Não mede mercado, preço ou receita.")
    cols[1].metric("Aderência ao Henrique", _text(row.get("personal_fit_label"), "Não demonstrado"), help="Inferência por correspondência com habilidades conhecidas.")
    cols[2].metric("Rastreabilidade", f"{int(_number(row.get('traceability_index')))}%", help="Completude de origem, URL, consulta e sinais observáveis.")
    cols[3].metric("Prontidão do plano", f"{int(_number(row.get('validation_readiness_index')))}%", help="Preenchimento do contrato de validação; não é validação comercial.")
    if _text(row.get("url")):
        actions = st.columns([1, 1, 3])
        actions[0].link_button("Abrir original", _text(row.get("url")), use_container_width=True)
        if actions[1].button(
            "Trabalhar agora",
            type="primary",
            use_container_width=True,
            key=f"work_now_{widget_scope}_{opportunity_key}",
        ):
            st.session_state["selected_opportunity_key"] = str(row["opportunity_key"])
            st.toast("Sinal selecionado. Abra a aba Decisão.", icon="🎯")


def main() -> None:
    st.set_page_config(
        page_title="Opportunity Radar",
        page_icon="📡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ensure_curation_schema(CURATION_DB)
    ensure_product_schema(PRODUCT_DB)

    available_paths = [
        path
        for path in discover_databases(DATA_DIR)
        if path.name != PRODUCT_DATABASE_NAME
    ]
    available_files = [path.name for path in available_paths]
    if not available_files:
        st.error("Nenhum banco operacional foi encontrado. Execute a coleta real antes de abrir a dashboard.")
        st.stop()

    dataset = cached_radar_data(str(DATA_DIR), tuple(available_files))
    curation = cached_curation(str(CURATION_DB), CURATION_DB.stat().st_mtime_ns)
    workspaces, evidence, events, translations = cached_product_data(
        str(PRODUCT_DB), PRODUCT_DB.stat().st_mtime_ns
    )

    opportunities = attach_curation(_consolidate(dataset.opportunities), curation)
    assessed = assess_frame(
        opportunities,
        workspaces=workspaces,
        evidence=evidence,
        events=events,
    )
    summary = build_landing_summary(
        opportunities,
        dataset.expansion_runs,
        dataset.variations,
        dataset.source_sync_runs,
    )
    metrics = quality_metrics(assessed)

    with st.sidebar:
        st.markdown("## 📡 Opportunity Radar")
        st.caption("Do sinal público à possível primeira receita")
        if st.button("Atualizar dados", type="primary", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        source_options = _unique_nonempty(assessed.get("source", pd.Series(dtype=str)))
        selected_sources = st.multiselect("Fontes", source_options, default=source_options)
        fit_options = _unique_nonempty(assessed.get("personal_fit_label", pd.Series(dtype=str)))
        selected_fit = st.multiselect("Aderência ao Henrique", fit_options, default=fit_options)
        lifecycle_options = _unique_nonempty(assessed.get("lifecycle_label", pd.Series(dtype=str)))
        selected_lifecycle = st.multiselect("Etapa", lifecycle_options, default=lifecycle_options)
        curation_options = list(CURATION_LABELS.values())
        selected_curation = st.multiselect("Curadoria", curation_options, default=curation_options)
        minimum_score = st.slider("Score de descoberta mínimo", 0.0, 100.0, 0.0, 1.0)
        search = st.text_input("Buscar", placeholder="planilha, suporte, integração...")
        st.divider()
        st.caption(f"Banco operacional: {len(available_files)} arquivo(s)")
        st.caption("Runner V2 preservado")

    filtered = assessed.copy()
    if selected_sources:
        filtered = filtered[filtered["source"].isin(selected_sources)]
    if selected_fit:
        filtered = filtered[filtered["personal_fit_label"].isin(selected_fit)]
    if selected_lifecycle:
        filtered = filtered[filtered["lifecycle_label"].isin(selected_lifecycle)]
    if selected_curation and "curation_label" in filtered:
        filtered = filtered[filtered["curation_label"].isin(selected_curation)]
    filtered = filtered[
        pd.to_numeric(filtered.get("discovery_score", 0), errors="coerce").fillna(0).ge(minimum_score)
    ]
    if search.strip():
        haystack = (
            filtered.get("title", "").astype(str)
            + " "
            + filtered.get("pain_categories", "").astype(str)
            + " "
            + filtered.get("original_queries", "").astype(str)
        )
        filtered = filtered[haystack.str.contains(search.strip(), case=False, regex=False)]

    operation_label = {
        "SUCCESS": "Ciclo concluído",
        "DEGRADED": "Operação degradada",
        "FAILED": "Ciclo com falha",
    }.get(summary.operation_status, "Estado não confirmado")
    operation_class = "chip-green" if summary.operation_status == "SUCCESS" else "chip-yellow"
    cycle_display = summary.cycle_id[:8] if summary.cycle_id else "sem ID"

    st.markdown(
        f"""
        <section class="radar-hero">
          <div class="kicker">Opportunity Radar · sistema pessoal de execução</div>
          <h1>Da dor pública à <span>próxima decisão.</span><br>Da validação à possível renda extra.</h1>
          <p>{html.escape(OFFICIAL_PRODUCT_DEFINITION.job_to_be_done)} O sistema separa dado, evidência, inferência, hipótese e decisão humana para evitar construir sem demanda.</p>
          <div>
            <span class="chip {operation_class}">● {html.escape(operation_label)}</span>
            <span class="chip">6 fontes conectadas</span>
            <span class="chip">Ciclo {html.escape(cycle_display)}</span>
            <span class="chip">Atualização {html.escape(summary.latest_at)}</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    top_metrics = st.columns(5)
    top_metrics[0].metric("Sinais detectados", metrics["signals"], help="Itens consolidados para análise; ainda não são negócios confirmados.")
    top_metrics[1].metric("Revisados", metrics["reviewed"], help="Itens rotulados como válidos ou falsos positivos.")
    top_metrics[2].metric("Oportunidades qualificadas", metrics["qualified"], help="Exigem decisão humana, comprador e evidência registrada.")
    in_validation = int(assessed.get("lifecycle_state", pd.Series(dtype=str)).isin({"test_planned", "validating", "interest_confirmed", "price_tested", "mvp_approved", "building"}).sum())
    top_metrics[3].metric("Em validação", in_validation)
    revenue_total = float(pd.to_numeric(events.get("amount_brl", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not events.empty else 0.0
    top_metrics[4].metric("Receita registrada", f"R$ {revenue_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), help="Somente eventos reais registrados como receita.")

    tabs = st.tabs(
        [
            "Início",
            "Decisão",
            "Validação",
            "Oportunidades",
            "Curadoria",
            "Métricas",
            "Consultas",
            "Execuções",
            "Área técnica",
        ]
    )
    (
        home_tab,
        decision_tab,
        validation_tab,
        opportunities_tab,
        curation_tab,
        metrics_tab,
        queries_tab,
        executions_tab,
        technical_tab,
    ) = tabs

    with home_tab:
        st.markdown('<div class="section-title">A próxima decisão do Henrique</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-copy">O ranking usa uma regra rastreável: decisão de curadoria, aderência ao perfil, rastreabilidade e só então score de descoberta. Não existe projeção automática de faturamento.</div>', unsafe_allow_html=True)
        next_row = select_next_opportunity(filtered)
        if next_row.empty:
            st.info("Nenhum sinal elegível para decisão.")
        else:
            selected = next_row.iloc[0]
            _render_decision_card(selected, widget_scope="home")
            _render_knowledge_block("", "Dado coletado", f"Fonte: {_text(selected.get('source'))}; título e URL preservados.")
            _render_knowledge_block("evidence", "Evidência atual", f"Rastreabilidade {int(_number(selected.get('traceability_index')))}%; sinais: {_text(selected.get('pain_categories'), 'não informados')}.")
            _render_knowledge_block("inference", "Inferência do sistema", f"Aderência ao Henrique: {_text(selected.get('personal_fit_label'))}. Base: {_text(selected.get('personal_fit_signals'), 'nenhum sinal identificado')}.")
            _render_knowledge_block("hypothesis", "Hipótese ainda não validada", _text(selected.get("buyer_hypothesis"), "Comprador, preço e monetização ainda precisam ser registrados e testados."))
            _render_knowledge_block("decision", "Decisão humana", f"Curadoria: {_text(selected.get('curation_label'), 'Pendente')}; etapa: {_text(selected.get('lifecycle_label'))}.")

        st.markdown('<div class="section-title">Caminho até a primeira receita</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-copy">O radar não termina na ideia. Cada avanço exige evidência e uma decisão registrada.</div>', unsafe_allow_html=True)
        current_state = _text(next_row.iloc[0].get("lifecycle_state"), "detected") if not next_row.empty else "detected"
        _render_lifecycle(current_state)

        st.markdown('<div class="section-title">Contrato de honestidade</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="score-note"><b>Score de descoberta ≠ mercado.</b> Ele mede força heurística de um sinal público. Comprador, disposição a pagar, custo, prazo e receita permanecem desconhecidos até serem validados.</div>',
            unsafe_allow_html=True,
        )
        health_cols = st.columns(2)
        with health_cols[0]:
            st.markdown("### Saúde do último ciclo")
            st.metric("Consultas concluídas", f"{summary.queries_completed}/{summary.queries_total}")
            st.metric("Variações processadas", f"{summary.variations_completed}/{summary.variations_total}")
            st.metric("Duplicações removidas", summary.duplicates_removed)
        with health_cols[1]:
            st.markdown("### Situação das fontes")
            _render_source_health(dataset.source_sync_runs)

    with decision_tab:
        st.header("Decisão e plano de validação")
        st.caption("Transforme um sinal em um contrato explícito de investigação. Campos vazios significam desconhecido.")
        row = _selected_row(filtered if not filtered.empty else assessed, "decision")
        if row is not None:
            key = str(row["opportunity_key"])
            workspace = _workspace_for(workspaces, key)
            _render_decision_card(row, widget_scope="decision")
            _render_lifecycle(_text(workspace.get("lifecycle_state"), "detected"))
            detail_cols = st.columns(2)
            with detail_cols[0]:
                _workspace_form(row, workspace)
            with detail_cols[1]:
                _translation_form(row, translations)
                st.markdown("### Por que combina com Henrique?")
                st.write(_text(row.get("personal_fit_signals"), "Nenhuma correspondência demonstrada."))
                st.caption("Inferência heurística. Henrique mantém a decisão final.")

    with validation_tab:
        st.header("Validação comercial")
        st.caption("Registre fatos observáveis: contatos, entrevistas, resposta à oferta, preço, custo, horas e receita.")
        row = _selected_row(assessed, "validation")
        if row is not None:
            key = str(row["opportunity_key"])
            _evidence_and_event_forms(row)
            st.markdown("### Evidências registradas")
            opportunity_evidence = evidence[evidence["opportunity_key"].astype(str).eq(key)] if not evidence.empty else pd.DataFrame()
            if opportunity_evidence.empty:
                st.info("Nenhuma evidência comercial registrada.")
            else:
                st.dataframe(opportunity_evidence, use_container_width=True, hide_index=True)
            st.markdown("### Ações e resultados")
            opportunity_events = events[events["opportunity_key"].astype(str).eq(key)] if not events.empty else pd.DataFrame()
            if opportunity_events.empty:
                st.info("Nenhum evento de validação registrado.")
            else:
                st.dataframe(opportunity_events, use_container_width=True, hide_index=True)

    with opportunities_tab:
        st.header("Sinais e oportunidades")
        st.caption("A lista distingue score de descoberta, aderência pessoal, rastreabilidade, etapa e decisão humana.")
        _render_opportunity_table(filtered)

    with curation_tab:
        st.header("Curadoria humana")
        st.caption("A curadoria cria o conjunto rotulado usado para medir precisão e falsos positivos.")
        row = _selected_row(assessed, "curation")
        if row is not None:
            url = _text(row.get("url"))
            st.subheader(_text(row.get("title"), "Sem título"))
            detail = st.columns(4)
            detail[0].metric("Fonte", _text(row.get("source"), "—"))
            detail[1].metric("Score", f"{_number(row.get('discovery_score')):.1f}")
            detail[2].metric("Aderência", _text(row.get("personal_fit_label"), "—"))
            detail[3].metric("Etapa", _text(row.get("lifecycle_label"), "—"))
            if url:
                st.link_button("Abrir conteúdo original", url, use_container_width=True)
            current_status = _text(row.get("curation_status"), "unreviewed")
            current_label = CURATION_LABELS.get(current_status, CURATION_LABELS["unreviewed"])
            status_label = st.radio(
                "Classificação",
                options=list(CURATION_LABELS.values()),
                index=list(CURATION_LABELS.values()).index(current_label),
                horizontal=True,
            )
            note_key = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12] if url else str(row["opportunity_key"])[:12]
            notes = st.text_area(
                "Motivo e evidências da decisão",
                value=_text(row.get("curation_notes")),
                placeholder="Por que é válida, precisa de análise ou é falso positivo?",
                key=f"curation_notes_{note_key}",
            )
            if st.button("Salvar curadoria", type="primary", use_container_width=True, disabled=not bool(url)):
                save_curation(CURATION_DB, url, LABEL_TO_STATUS[status_label], notes)
                st.cache_data.clear()
                st.toast("Curadoria salva.", icon="✅")
                st.rerun()

    with metrics_tab:
        st.header("Qualidade do produto")
        st.caption("Métricas comerciais permanecem vazias até existirem ações reais. Métricas técnicas não substituem resultado de produto.")
        m = quality_metrics(assessed)
        metric_cols = st.columns(5)
        metric_cols[0].metric("Sinais", m["signals"])
        metric_cols[1].metric("Rotulados", m["reviewed"])
        metric_cols[2].metric("Válidos", m["valid"])
        metric_cols[3].metric("Falsos positivos", m["false_positive"])
        metric_cols[4].metric("Precision rotulada", _format_percent(m["precision"]))
        st.metric("Precision@10", _format_percent(m["precision_at_k"]), help="Calculada apenas sobre itens rotulados presentes no top 10.")
        if m["reviewed"] == 0:
            st.warning("Baseline de qualidade ainda não existe. Rotule oportunidades válidas e falsos positivos.")
        else:
            chart_data = pd.DataFrame(
                {"Classe": ["Válida", "Falso positivo"], "Quantidade": [m["valid"], m["false_positive"]]}
            )
            chart = alt.Chart(chart_data).mark_bar(cornerRadiusEnd=5).encode(
                x=alt.X("Quantidade:Q", axis=alt.Axis(tickMinStep=1)),
                y=alt.Y("Classe:N", sort="-x", title=None),
                tooltip=["Classe", "Quantidade"],
            )
            st.altair_chart(chart, use_container_width=True)
        st.markdown("### Pipeline de validação")
        if workspaces.empty:
            st.info("Nenhuma oportunidade entrou no ciclo de validação.")
        else:
            pipeline = (
                workspaces.assign(
                    etapa=workspaces["lifecycle_state"].astype(str).map(LIFECYCLE_LABELS).fillna("Desconhecida")
                )
                .groupby("etapa")
                .size()
                .rename("oportunidades")
                .reset_index()
            )
            st.dataframe(pipeline, use_container_width=True, hide_index=True)

    with queries_tab:
        st.header("Consultas e variações")
        st.caption("Rastreabilidade operacional preservada.")
        st.subheader("Consultas")
        if dataset.expansion_runs.empty:
            st.info("Nenhuma execução de consulta encontrada.")
        else:
            st.dataframe(dataset.expansion_runs, use_container_width=True, hide_index=True, height=420)
        st.subheader("Variações")
        if dataset.variations.empty:
            st.info("Nenhuma variação encontrada.")
        else:
            st.dataframe(dataset.variations, use_container_width=True, hide_index=True, height=520)

    with executions_tab:
        st.header("Execuções")
        st.caption("Saúde técnica e falhas permanecem visíveis; stdout, stderr e tracebacks não são ocultados pelo processo operacional.")
        if dataset.collection_runs.empty:
            st.info("Nenhuma collection_run encontrada.")
        else:
            st.dataframe(dataset.collection_runs, use_container_width=True, hide_index=True)
        if not dataset.source_sync_runs.empty:
            st.subheader("Sincronizações por fonte")
            st.dataframe(dataset.source_sync_runs, use_container_width=True, hide_index=True)

    with technical_tab:
        st.header("Área técnica")
        st.caption("Inventário dos bancos operacionais. SQLite, cache, logs e segredos permanecem fora do Git.")
        st.code(f"Dados: {DATA_DIR}\nCuradoria: {CURATION_DB}\nProduto: {PRODUCT_DB}")
        st.subheader("Bancos")
        st.dataframe(dataset.databases, use_container_width=True, hide_index=True)
        st.subheader("Inventário de tabelas")
        if dataset.inventory.empty:
            st.info("Nenhuma tabela encontrada.")
        else:
            st.dataframe(dataset.inventory, use_container_width=True, hide_index=True, height=540)


if __name__ == "__main__":
    main()
