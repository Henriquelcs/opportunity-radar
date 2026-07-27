from __future__ import annotations

import hashlib
import html
import os
import re
import sys
from pathlib import Path

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
from src.dashboard.presentation import (
    LandingSummary,
    build_landing_summary,
    rank_opportunities,
    source_status_overview,
)


st.set_page_config(
    page_title="Opportunity Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        :root {
            --radar-accent: #66e3c4;
            --radar-accent-strong: #22c7a5;
            --radar-blue: #68a8ff;
            --radar-bg-soft: rgba(102, 227, 196, 0.08);
            --radar-border: rgba(148, 163, 184, 0.22);
            --radar-muted: #8d98aa;
        }

        .block-container {
            max-width: 1380px;
            padding-top: 1rem;
            padding-bottom: 4rem;
        }

        [data-testid="stSidebar"] {
            border-right: 1px solid var(--radar-border);
        }

        [data-testid="stSidebar"] .block-container {
            padding-top: 1.35rem;
        }

        .sidebar-brand {
            padding: 0.2rem 0 1rem 0;
        }

        .sidebar-brand strong {
            display: block;
            font-size: 1.12rem;
            letter-spacing: -0.02em;
        }

        .sidebar-brand span {
            color: var(--radar-muted);
            font-size: 0.82rem;
        }

        .radar-hero {
            position: relative;
            overflow: hidden;
            padding: clamp(1.7rem, 4vw, 3.4rem);
            border: 1px solid rgba(102, 227, 196, 0.24);
            border-radius: 28px;
            background:
                radial-gradient(
                    circle at 82% 20%,
                    rgba(104, 168, 255, 0.20),
                    transparent 34%
                ),
                radial-gradient(
                    circle at 12% 88%,
                    rgba(102, 227, 196, 0.16),
                    transparent 38%
                ),
                linear-gradient(
                    135deg,
                    rgba(15, 23, 42, 0.98),
                    rgba(9, 16, 29, 0.96)
                );
            box-shadow: 0 24px 70px rgba(0, 0, 0, 0.22);
            margin-bottom: 1.15rem;
        }

        .radar-hero::after {
            content: "";
            position: absolute;
            width: 280px;
            height: 280px;
            right: -90px;
            bottom: -120px;
            border-radius: 50%;
            border: 1px solid rgba(102, 227, 196, 0.18);
            box-shadow:
                0 0 0 35px rgba(102, 227, 196, 0.025),
                0 0 0 75px rgba(104, 168, 255, 0.025);
        }

        .hero-kicker {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            color: var(--radar-accent);
            font-size: 0.78rem;
            font-weight: 800;
            letter-spacing: 0.11em;
            text-transform: uppercase;
            margin-bottom: 0.8rem;
        }

        .radar-hero h1 {
            max-width: 880px;
            margin: 0;
            color: #f8fafc;
            font-size: clamp(2.15rem, 5vw, 4.2rem);
            line-height: 1.02;
            letter-spacing: -0.055em;
        }

        .radar-hero h1 span {
            color: var(--radar-accent);
        }

        .radar-hero p {
            max-width: 760px;
            margin: 1.15rem 0 1.25rem 0;
            color: #b8c3d3;
            font-size: clamp(1rem, 1.4vw, 1.16rem);
            line-height: 1.65;
        }

        .hero-meta {
            display: flex;
            flex-wrap: wrap;
            gap: 0.65rem;
            align-items: center;
        }

        .status-pill,
        .hero-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.38rem;
            padding: 0.48rem 0.72rem;
            border-radius: 999px;
            border: 1px solid var(--radar-border);
            font-size: 0.78rem;
            font-weight: 700;
        }

        .status-success {
            color: #79e7bd;
            background: rgba(34, 197, 94, 0.10);
            border-color: rgba(34, 197, 94, 0.22);
        }

        .status-degraded {
            color: #f7c66f;
            background: rgba(245, 158, 11, 0.10);
            border-color: rgba(245, 158, 11, 0.22);
        }

        .status-failed {
            color: #ff8c8c;
            background: rgba(239, 68, 68, 0.10);
            border-color: rgba(239, 68, 68, 0.22);
        }

        .hero-chip {
            color: #cbd5e1;
            background: rgba(255, 255, 255, 0.035);
        }

        [data-testid="stMetric"] {
            border: 1px solid var(--radar-border);
            border-radius: 18px;
            padding: 16px 18px;
            background:
                linear-gradient(
                    145deg,
                    rgba(102, 227, 196, 0.055),
                    rgba(104, 168, 255, 0.025)
                );
            min-height: 116px;
        }

        [data-testid="stMetricLabel"] {
            color: var(--radar-muted);
        }

        [data-testid="stMetricValue"] {
            letter-spacing: -0.04em;
        }

        .section-heading {
            margin-top: 2.25rem;
            margin-bottom: 0.35rem;
            font-size: clamp(1.55rem, 2.5vw, 2.1rem);
            letter-spacing: -0.035em;
        }

        .section-copy {
            color: var(--radar-muted);
            margin-bottom: 1rem;
            max-width: 820px;
        }

        .opportunity-tag {
            display: inline-block;
            padding: 0.28rem 0.52rem;
            border-radius: 999px;
            background: var(--radar-bg-soft);
            color: var(--radar-accent);
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.045em;
            margin-right: 0.35rem;
        }

        .opportunity-score {
            color: #f8fafc;
            font-size: 0.78rem;
            font-weight: 800;
        }

        .opportunity-title {
            min-height: 4.8rem;
            margin: 0.8rem 0 0.5rem 0;
            font-size: 1.08rem;
            font-weight: 800;
            line-height: 1.42;
            letter-spacing: -0.02em;
        }

        .opportunity-context {
            min-height: 3.6rem;
            color: var(--radar-muted);
            font-size: 0.84rem;
            line-height: 1.45;
        }

        .step-number {
            display: inline-flex;
            width: 2rem;
            height: 2rem;
            align-items: center;
            justify-content: center;
            border-radius: 50%;
            background: var(--radar-bg-soft);
            color: var(--radar-accent);
            font-weight: 900;
            margin-bottom: 0.55rem;
        }

        .step-title {
            font-size: 1.02rem;
            font-weight: 800;
            margin-bottom: 0.3rem;
        }

        .step-copy {
            color: var(--radar-muted);
            font-size: 0.88rem;
            line-height: 1.55;
        }

        .status-note {
            padding: 0.85rem 1rem;
            border: 1px solid var(--radar-border);
            border-radius: 14px;
            color: var(--radar-muted);
            background: rgba(148, 163, 184, 0.035);
        }

        .technical-caption {
            color: var(--radar-muted);
            font-size: 0.9rem;
        }

        div[data-testid="stDataFrame"] {
            border: 1px solid rgba(148, 163, 184, 0.12);
            border-radius: 14px;
            overflow: hidden;
        }

        div[data-testid="stVerticalBlockBorderWrapper"] {
            border-color: var(--radar-border);
            border-radius: 18px;
            background: rgba(148, 163, 184, 0.025);
        }

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] code {
            white-space: normal;
            word-break: break-all;
        }

        @media (max-width: 760px) {
            .radar-hero {
                border-radius: 21px;
                padding: 1.45rem;
            }

            .radar-hero h1 {
                font-size: 2.2rem;
            }

            .opportunity-title,
            .opportunity-context {
                min-height: auto;
            }
        }
    </style>
    """,
    unsafe_allow_html=True,
)

DATA_DIR = Path(
    os.getenv("OPPORTUNITY_RADAR_DATA_DIR", str(PROJECT_DIR / "data"))
).resolve()
CURATION_DB = DATA_DIR / "opportunity_radar_curation.db"


@st.cache_data(ttl=20, show_spinner=False)
def cached_load(data_dir: str, selected_files: tuple[str, ...]):
    return load_radar_data(data_dir, selected_files)


@st.cache_data(ttl=5, show_spinner=False)
def cached_load_curation(database_path: str, modified_ns: int) -> pd.DataFrame:
    del modified_ns
    return load_curation(database_path)


def unique_nonempty(series: pd.Series) -> list[str]:
    values = {
        str(value).strip()
        for value in series.astype("string").fillna("").tolist()
        if str(value).strip()
    }
    return sorted(values, key=str.casefold)


def consolidate_global(opportunities: pd.DataFrame) -> pd.DataFrame:
    if opportunities.empty:
        return opportunities.copy()

    result = opportunities.copy()
    result["score_sort"] = pd.to_numeric(result["score"], errors="coerce")
    result["has_query"] = (
        result["original_queries"]
        .astype("string")
        .fillna("")
        .astype(str)
        .ne("")
    )
    result = result.sort_values(
        ["has_query", "score_sort", "match_count"],
        ascending=[False, False, False],
        na_position="last",
    )
    url_key = (
        result["url"]
        .astype("string")
        .fillna("")
        .astype(str)
        .str.strip()
    )
    title_key = (
        result["title"]
        .astype("string")
        .fillna("")
        .astype(str)
        .str.casefold()
        .str.strip()
    )
    result["global_key"] = url_key.mask(url_key.eq(""), title_key)
    result = result.drop_duplicates("global_key", keep="first")
    return result.drop(
        columns=["score_sort", "has_query", "global_key"]
    )


def render_table(frame: pd.DataFrame, height: int = 560) -> None:
    if frame.empty:
        st.info("Nenhuma oportunidade disponível para os filtros selecionados.")
        return

    visible_columns = [
        column
        for column in [
            "title",
            "source",
            "score",
            "level",
            "curation_label",
            "original_queries",
            "matched_queries",
            "match_count",
            "pain_categories",
            "url",
        ]
        if column in frame.columns
    ]
    display = frame[visible_columns].copy()
    if "score" in display:
        display["score"] = pd.to_numeric(
            display["score"],
            errors="coerce",
        ).round(2)

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=height,
        column_config={
            "title": st.column_config.TextColumn(
                "Oportunidade",
                width="large",
            ),
            "source": st.column_config.TextColumn(
                "Fonte",
                width="small",
            ),
            "score": st.column_config.NumberColumn(
                "Score",
                format="%.2f",
            ),
            "level": st.column_config.TextColumn(
                "Nível",
                width="small",
            ),
            "curation_label": st.column_config.TextColumn(
                "Curadoria",
                width="medium",
            ),
            "original_queries": st.column_config.TextColumn(
                "Consulta original",
                width="large",
            ),
            "matched_queries": st.column_config.TextColumn(
                "Variação encontrada",
                width="large",
            ),
            "match_count": st.column_config.NumberColumn(
                "Matches",
                format="%d",
            ),
            "pain_categories": st.column_config.TextColumn(
                "Sinais de dor",
                width="large",
            ),
            "url": st.column_config.LinkColumn(
                "Fonte pública",
                display_text="Abrir oportunidade",
                width="medium",
            ),
        },
    )


def horizontal_count_chart(
    frame: pd.DataFrame,
    label_column: str,
    value_column: str,
) -> alt.Chart:
    return (
        alt.Chart(frame)
        .mark_bar(cornerRadiusEnd=5)
        .encode(
            x=alt.X(
                f"{value_column}:Q",
                title="Oportunidades",
                axis=alt.Axis(tickMinStep=1),
            ),
            y=alt.Y(
                f"{label_column}:N",
                title=None,
                sort="-x",
                axis=alt.Axis(labelLimit=520),
            ),
            tooltip=[
                alt.Tooltip(f"{label_column}:N", title="Item"),
                alt.Tooltip(
                    f"{value_column}:Q",
                    title="Oportunidades",
                ),
            ],
        )
        .properties(height=max(150, min(420, 42 * len(frame))))
    )


def query_counts_for_filtered(
    filtered_opportunities: pd.DataFrame,
    matches: pd.DataFrame,
) -> pd.DataFrame:
    columns = ["consulta", "oportunidades"]
    if filtered_opportunities.empty:
        return pd.DataFrame(columns=columns)

    filtered_urls = {
        str(value).strip()
        for value in filtered_opportunities.get(
            "url",
            pd.Series(dtype=str),
        )
        if str(value).strip()
    }
    if not matches.empty and filtered_urls:
        relevant = matches[
            matches["opportunity_url"].astype(str).isin(filtered_urls)
        ].copy()
        relevant["original_query"] = (
            relevant["original_query"]
            .astype("string")
            .fillna("")
            .astype(str)
            .str.strip()
            .replace("", "Não informada")
        )
        if not relevant.empty:
            return (
                relevant.groupby("original_query")["opportunity_url"]
                .nunique()
                .sort_values(ascending=False)
                .rename("oportunidades")
                .reset_index()
                .rename(columns={"original_query": "consulta"})
            )

    records: list[dict[str, str]] = []
    for _, row in filtered_opportunities.iterrows():
        url = str(row.get("url", "") or "").strip()
        queries = str(row.get("original_queries", "") or "").split("|")
        for query in queries:
            normalized = query.strip()
            if normalized:
                records.append(
                    {
                        "consulta": normalized,
                        "url": url,
                    }
                )

    if not records:
        return pd.DataFrame(columns=columns)

    return (
        pd.DataFrame(records)
        .groupby("consulta")["url"]
        .nunique()
        .sort_values(ascending=False)
        .rename("oportunidades")
        .reset_index()
    )


def curation_counts(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(
            columns=["curadoria", "oportunidades"]
        )
    return (
        frame.groupby("curation_label")
        .size()
        .sort_values(ascending=False)
        .rename("oportunidades")
        .reset_index()
        .rename(columns={"curation_label": "curadoria"})
    )


def status_meta(summary: LandingSummary) -> tuple[str, str]:
    mapping = {
        "SUCCESS": ("Ciclo concluído", "status-success"),
        "DEGRADED": ("Operação degradada", "status-degraded"),
        "FAILED": ("Ciclo com falha", "status-failed"),
        "UNKNOWN": ("Aguardando ciclo", "status-degraded"),
    }
    return mapping.get(
        summary.operation_status,
        (summary.operation_status.title(), "status-degraded"),
    )


def display_score(raw_value: object) -> str:
    value = pd.to_numeric(
        pd.Series([raw_value]),
        errors="coerce",
    ).iloc[0]
    return "—" if pd.isna(value) else f"{float(value):.1f}"


def render_opportunity_card(row: pd.Series, position: int) -> None:
    title = html.escape(
        str(row.get("title", "") or "Oportunidade sem título")
    )
    source = html.escape(
        str(row.get("source", "") or "Fonte não informada")
    )
    score = display_score(row.get("score"))
    query = html.escape(
        str(row.get("original_queries", "") or "Consulta não informada")
    )
    pain = html.escape(
        str(row.get("pain_categories", "") or "Dor em análise")
    )
    url = str(row.get("url", "") or "").strip()

    with st.container(border=True):
        st.markdown(
            f"""
            <div>
                <span class="opportunity-tag">{source}</span>
                <span class="opportunity-score">Score {score}</span>
                <div class="opportunity-title">{title}</div>
                <div class="opportunity-context">
                    <strong>Dor pesquisada:</strong> {query}<br>
                    <strong>Sinais:</strong> {pain}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        score_number = pd.to_numeric(
            pd.Series([row.get("score")]),
            errors="coerce",
        ).fillna(0).iloc[0]
        st.progress(
            min(100, max(0, int(float(score_number)))),
            text="Força do sinal",
        )

        left, right = st.columns(2)
        with left:
            if url:
                st.link_button(
                    "Abrir fonte",
                    url,
                    use_container_width=True,
                )
            else:
                st.button(
                    "Sem URL",
                    key=f"landing_no_url_{position}",
                    disabled=True,
                    use_container_width=True,
                )
        with right:
            if st.button(
                "Analisar",
                key=f"landing_analyze_{position}_{hashlib.sha1(url.encode('utf-8')).hexdigest()[:8]}",
                type="primary",
                use_container_width=True,
                disabled=not bool(url),
            ):
                st.session_state["selected_opportunity_url"] = url
                st.toast(
                    "Oportunidade selecionada. Abra a aba Curadoria.",
                    icon="🎯",
                )


available_paths = discover_databases(DATA_DIR)
available_files = [path.name for path in available_paths]

if not available_files:
    st.error(
        "Nenhum banco SQLite de coleta foi encontrado na pasta data. "
        "Execute primeiro uma coleta real do Opportunity Radar."
    )
    st.stop()

ensure_curation_schema(CURATION_DB)
dataset = cached_load(
    str(DATA_DIR),
    tuple(available_files),
)
curation_mtime = CURATION_DB.stat().st_mtime_ns
curation = cached_load_curation(
    str(CURATION_DB),
    curation_mtime,
)

global_opportunities = attach_curation(
    consolidate_global(dataset.opportunities.copy()),
    curation,
)

with st.sidebar:
    st.markdown(
        """
        <div class="sidebar-brand">
            <strong>📡 Opportunity Radar</strong>
            <span>Descoberta de oportunidades para renda extra</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "Atualizar dados",
        type="primary",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.rerun()

    st.subheader("Filtros")

    source_options = unique_nonempty(
        global_opportunities.get(
            "source",
            pd.Series(dtype=str),
        )
    )
    selected_sources = st.multiselect(
        "Fontes com oportunidades",
        source_options,
        default=source_options,
    )

    query_values: set[str] = set()
    if "original_queries" in global_opportunities:
        for value in global_opportunities[
            "original_queries"
        ].astype("string").fillna(""):
            query_values.update(
                item.strip()
                for item in str(value).split("|")
                if item.strip()
            )
    query_options = sorted(query_values, key=str.casefold)
    selected_queries = st.multiselect(
        "Dores pesquisadas",
        query_options,
        default=query_options,
    )

    status_options = list(CURATION_LABELS.values())
    selected_status_labels = st.multiselect(
        "Curadoria",
        status_options,
        default=status_options,
    )

    score_values = pd.to_numeric(
        global_opportunities.get(
            "score",
            pd.Series(dtype=float),
        ),
        errors="coerce",
    ).dropna()
    max_score = (
        float(score_values.max())
        if not score_values.empty
        else 100.0
    )
    minimum_score = st.slider(
        "Score mínimo",
        min_value=0.0,
        max_value=max(100.0, max_score),
        value=0.0,
        step=1.0,
    )
    search_text = st.text_input(
        "Buscar oportunidade",
        placeholder="Ex.: planilha, suporte, formulário",
    )

    st.divider()
    st.caption(
        f"{len(available_files)} bancos SQLite carregados. "
        "A operação técnica permanece preservada."
    )

filtered = global_opportunities.copy()

if selected_sources and "source" in filtered:
    filtered = filtered[
        filtered["source"].isin(selected_sources)
    ]
if selected_queries and "original_queries" in filtered:
    pattern = "|".join(
        re.escape(query)
        for query in selected_queries
    )
    filtered = filtered[
        filtered["original_queries"]
        .astype("string")
        .fillna("")
        .astype(str)
        .str.contains(pattern, case=False, regex=True)
    ]
if selected_status_labels and "curation_label" in filtered:
    filtered = filtered[
        filtered["curation_label"].isin(selected_status_labels)
    ]
if "score" in filtered:
    numeric_score = pd.to_numeric(
        filtered["score"],
        errors="coerce",
    )
    filtered = filtered[
        numeric_score.isna()
        | numeric_score.ge(minimum_score)
    ]
if search_text.strip() and "title" in filtered:
    filtered = filtered[
        filtered["title"]
        .astype("string")
        .fillna("")
        .astype(str)
        .str.contains(
            search_text.strip(),
            case=False,
            regex=False,
        )
    ]

summary = build_landing_summary(
    global_opportunities,
    dataset.expansion_runs,
    dataset.variations,
    dataset.source_sync_runs,
)
status_label, status_class = status_meta(summary)
cycle_display = summary.cycle_id[:8] if summary.cycle_id else "sem ID"

st.markdown(
    f"""
    <section class="radar-hero">
        <div class="hero-kicker">Opportunity Radar · descoberta orientada a renda</div>
        <h1>
            Encontre dores reais.<br>
            Transforme-as em <span>renda extra.</span>
        </h1>
        <p>
            O radar coleta problemas públicos, organiza os sinais mais fortes e
            ajuda você a escolher uma solução pequena para validar antes de investir
            tempo e dinheiro.
        </p>
        <div class="hero-meta">
            <span class="status-pill {status_class}">
                ● {html.escape(status_label)}
            </span>
            <span class="hero-chip">
                6 fontes conectadas
            </span>
            <span class="hero-chip">
                Última atualização: {html.escape(summary.latest_at)}
            </span>
            <span class="hero-chip">
                Ciclo {html.escape(cycle_display)}
            </span>
        </div>
    </section>
    """,
    unsafe_allow_html=True,
)

hero_actions = st.columns([1.2, 1.2, 3.6])
with hero_actions[0]:
    if st.button(
        "Atualizar radar",
        key="hero_refresh",
        type="primary",
        use_container_width=True,
    ):
        st.cache_data.clear()
        st.rerun()
with hero_actions[1]:
    top_for_action = rank_opportunities(filtered, limit=1)
    if not top_for_action.empty:
        best_url = str(
            top_for_action.iloc[0].get("url", "") or ""
        ).strip()
        if best_url:
            st.link_button(
                "Abrir melhor sinal",
                best_url,
                use_container_width=True,
            )
        else:
            st.button(
                "Abrir melhor sinal",
                disabled=True,
                use_container_width=True,
            )

metrics = st.columns(4)
metrics[0].metric(
    "Oportunidades atuais",
    summary.opportunities,
    help="Oportunidades consolidadas por URL.",
)
metrics[1].metric(
    "Fontes com oportunidades",
    f"{summary.opportunity_sources}/{summary.connected_sources}",
    help="Fontes que geraram oportunidades no conjunto atual.",
)
metrics[2].metric(
    "Consultas no último ciclo",
    f"{summary.queries_completed}/{summary.queries_total}",
    help="Considera somente o ciclo mais recente, não o histórico legado.",
)
metrics[3].metric(
    "Variações processadas",
    f"{summary.variations_completed}/{summary.variations_total}",
    help="Variações válidas do último ciclo operacional.",
)

(
    landing_tab,
    analysis_tab,
    opportunities_tab,
    curation_tab,
    queries_tab,
    executions_tab,
    technical_tab,
) = st.tabs(
    [
        "Início",
        "Análise",
        "Oportunidades",
        "Curadoria",
        "Consultas",
        "Execuções",
        "Área técnica",
    ]
)

with landing_tab:
    st.markdown(
        '<h2 class="section-heading">Melhores oportunidades para validar agora</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="section-copy">'
        "Prioridade por score e recorrência do sinal. Títulos repetidos são "
        "consolidados nesta vitrine para facilitar a decisão."
        "</p>",
        unsafe_allow_html=True,
    )

    landing_opportunities = rank_opportunities(
        filtered,
        limit=6,
    )
    if landing_opportunities.empty:
        st.info(
            "Nenhuma oportunidade disponível com os filtros atuais."
        )
    else:
        rows = list(landing_opportunities.iterrows())
        for group_start in range(0, len(rows), 3):
            columns = st.columns(3)
            group = rows[group_start:group_start + 3]
            for offset, (card_column, (_, opportunity)) in enumerate(
                zip(columns, group)
            ):
                with card_column:
                    render_opportunity_card(
                        opportunity,
                        position=group_start + offset,
                    )

    st.markdown(
        '<h2 class="section-heading">Como transformar um sinal em renda</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="section-copy">'
        "O radar encontra a dor. A renda nasce quando você confirma o problema, "
        "entrega uma solução pequena e testa se alguém pagaria por ela."
        "</p>",
        unsafe_allow_html=True,
    )

    step_columns = st.columns(3)
    steps = (
        (
            "1",
            "Validar a dor",
            "Abra a fonte, confirme que o problema é real e procure sinais de repetição.",
        ),
        (
            "2",
            "Definir a menor solução",
            "Escolha uma automação, serviço ou ferramenta simples que resolva uma parte valiosa.",
        ),
        (
            "3",
            "Testar cobrança",
            "Converse com pessoas afetadas e valide preço antes de construir algo grande.",
        ),
    )
    for column, (number, title, copy) in zip(
        step_columns,
        steps,
    ):
        with column:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div class="step-number">{number}</div>
                    <div class="step-title">{html.escape(title)}</div>
                    <div class="step-copy">{html.escape(copy)}</div>
                    """,
                    unsafe_allow_html=True,
                )

    st.markdown(
        '<h2 class="section-heading">Fontes e última coleta</h2>',
        unsafe_allow_html=True,
    )
    source_column, operation_column = st.columns([1.5, 1])
    with source_column:
        source_frame = source_status_overview(
            dataset.source_sync_runs
        )
        st.dataframe(
            source_frame,
            use_container_width=True,
            hide_index=True,
            height=252,
            column_config={
                "Fonte": st.column_config.TextColumn(
                    "Fonte conectada",
                    width="medium",
                ),
                "Estado": st.column_config.TextColumn(
                    "Último ciclo",
                    width="medium",
                ),
                "Itens disponíveis": st.column_config.NumberColumn(
                    "Itens",
                    format="%d",
                ),
                "Novos no ciclo": st.column_config.NumberColumn(
                    "Novos",
                    format="%d",
                ),
            },
        )

    with operation_column:
        with st.container(border=True):
            st.markdown("#### Resumo operacional")
            operation_metrics = st.columns(2)
            operation_metrics[0].metric(
                "Fontes ao vivo",
                summary.live_sources,
            )
            operation_metrics[1].metric(
                "Fontes em cache",
                summary.cached_sources,
            )
            operation_metrics[0].metric(
                "Duplicações removidas",
                summary.duplicates_removed,
            )
            operation_metrics[1].metric(
                "Aguardando curadoria",
                summary.pending_review,
            )
            st.markdown(
                '<div class="status-note">'
                "Cache não significa falha total. O Runner V2 preserva dados "
                "válidos e mantém a análise disponível durante limites temporários."
                "</div>",
                unsafe_allow_html=True,
            )

with analysis_tab:
    st.subheader("Análise consolidada")
    st.caption(
        "Os gráficos respeitam os filtros da barra lateral."
    )

    left, right = st.columns(2)

    with left:
        st.subheader("Oportunidades por fonte")
        if not filtered.empty and "source" in filtered:
            source_counts = (
                filtered.assign(
                    source=filtered["source"].replace(
                        "",
                        "Não informada",
                    )
                )
                .groupby("source")
                .size()
                .sort_values(ascending=False)
                .rename("oportunidades")
                .reset_index()
            )
            st.altair_chart(
                horizontal_count_chart(
                    source_counts,
                    "source",
                    "oportunidades",
                ),
                use_container_width=True,
            )
        else:
            st.info(
                "Sem dados de fonte para os filtros selecionados."
            )

    with right:
        st.subheader("Oportunidades por dor pesquisada")
        query_counts = query_counts_for_filtered(
            filtered,
            dataset.matches,
        )
        if query_counts.empty:
            st.info(
                "Sem rastreabilidade de consulta para os filtros selecionados."
            )
        else:
            st.altair_chart(
                horizontal_count_chart(
                    query_counts,
                    "consulta",
                    "oportunidades",
                ),
                use_container_width=True,
            )

    curation_frame = curation_counts(filtered)
    if not curation_frame.empty:
        st.subheader("Situação da curadoria")
        st.altair_chart(
            horizontal_count_chart(
                curation_frame,
                "curadoria",
                "oportunidades",
            ),
            use_container_width=True,
        )

    st.subheader("Oportunidades em destaque")
    render_table(
        rank_opportunities(filtered, limit=15),
        height=520,
    )

with opportunities_tab:
    st.subheader("Oportunidades consolidadas")
    st.caption(
        "Esta visão preserva os dados atuais. Uma URL aparece apenas uma vez; "
        "consultas e variações continuam rastreáveis."
    )
    render_table(filtered, height=700)

with curation_tab:
    st.subheader("Detalhes e curadoria")
    st.caption(
        "Classifique o que merece validação comercial e registre suas observações."
    )

    reviewable = filtered[
        filtered.get(
            "url",
            pd.Series(
                index=filtered.index,
                dtype=str,
            ),
        )
        .astype("string")
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    if reviewable.empty:
        st.info(
            "Nenhuma oportunidade com URL está disponível para revisão."
        )
    else:
        reviewable["_score"] = pd.to_numeric(
            reviewable.get(
                "score",
                pd.Series(
                    index=reviewable.index,
                    dtype=float,
                ),
            ),
            errors="coerce",
        )
        reviewable = reviewable.sort_values(
            ["_score", "title"],
            ascending=[False, True],
            na_position="last",
        ).drop(columns="_score")

        title_by_url = {
            str(row["url"]): str(
                row.get("title", "") or row["url"]
            )
            for _, row in reviewable.iterrows()
        }
        options = list(title_by_url)
        preferred_url = str(
            st.session_state.get(
                "selected_opportunity_url",
                "",
            )
            or ""
        )
        selected_index = (
            options.index(preferred_url)
            if preferred_url in options
            else 0
        )

        selected_url = st.selectbox(
            "Selecione uma oportunidade",
            options=options,
            index=selected_index,
            format_func=lambda value: title_by_url[value],
        )
        st.session_state["selected_opportunity_url"] = selected_url
        selected_row = reviewable[
            reviewable["url"].eq(selected_url)
        ].iloc[0]

        with st.container(border=True):
            st.markdown(
                f"### {selected_row.get('title', 'Sem título')}"
            )
            detail_columns = st.columns(4)
            detail_columns[0].metric(
                "Fonte",
                str(
                    selected_row.get("source", "")
                    or "Não informada"
                ),
            )
            detail_columns[1].metric(
                "Score",
                display_score(selected_row.get("score")),
            )
            detail_columns[2].metric(
                "Nível",
                str(
                    selected_row.get("level", "")
                    or "Não informado"
                ),
            )
            detail_columns[3].metric(
                "Matches",
                int(
                    selected_row.get("match_count", 0)
                    or 0
                ),
            )

            st.markdown(
                "**Dor pesquisada:** "
                f"{selected_row.get('original_queries', '') or 'Não informada'}"
            )
            st.markdown(
                "**Variações que encontraram:** "
                f"{selected_row.get('matched_queries', '') or 'Não informada'}"
            )
            st.markdown(
                "**Sinais de dor:** "
                f"{selected_row.get('pain_categories', '') or 'Não informados'}"
            )
            st.link_button(
                "Abrir oportunidade na fonte pública",
                selected_url,
                use_container_width=True,
            )

        current_status = str(
            selected_row.get(
                "curation_status",
                "unreviewed",
            )
            or "unreviewed"
        )
        current_label = CURATION_LABELS.get(
            current_status,
            CURATION_LABELS["unreviewed"],
        )
        status_label = st.radio(
            "Classificação",
            options=list(CURATION_LABELS.values()),
            index=list(
                CURATION_LABELS.values()
            ).index(current_label),
            horizontal=True,
        )
        note_key = hashlib.sha1(
            selected_url.encode("utf-8")
        ).hexdigest()[:12]
        notes = st.text_area(
            "Observações",
            value=str(
                selected_row.get(
                    "curation_notes",
                    "",
                )
                or ""
            ),
            placeholder=(
                "Registre evidências da dor, público afetado, "
                "hipótese de solução e disposição a pagar."
            ),
            key=f"curation_notes_{note_key}",
        )
        if st.button(
            "Salvar classificação",
            type="primary",
            use_container_width=True,
        ):
            save_curation(
                CURATION_DB,
                selected_url,
                LABEL_TO_STATUS[status_label],
                notes,
            )
            st.cache_data.clear()
            st.toast(
                "Classificação salva.",
                icon="✅",
            )
            st.rerun()

with queries_tab:
    st.subheader("Execuções de expansão")
    st.caption(
        "Histórico completo preservado para rastreabilidade."
    )
    if dataset.expansion_runs.empty:
        st.info(
            "Nenhum histórico de expansão encontrado."
        )
    else:
        run_columns = [
            column
            for column in [
                "database_file",
                "id",
                "original_query",
                "status",
                "variation_count",
                "successful_variations",
                "failed_variations",
                "unique_opportunities",
                "total_matches",
                "duplicate_matches",
                "started_at",
                "finished_at",
            ]
            if column in dataset.expansion_runs.columns
        ]
        st.dataframe(
            dataset.expansion_runs[run_columns],
            use_container_width=True,
            hide_index=True,
            column_config={
                "original_query": st.column_config.TextColumn(
                    "Consulta original",
                    width="large",
                ),
                "database_file": st.column_config.TextColumn(
                    "Banco",
                    width="large",
                ),
            },
        )

    st.subheader("Variações executadas")
    if dataset.variations.empty:
        st.info("Nenhuma variação encontrada.")
    else:
        variation_columns = [
            column
            for column in [
                "database_file",
                "expansion_run_id",
                "position",
                "query",
                "is_original",
                "status",
                "pipeline_status",
                "attempt_count",
                "collected_matches",
                "new_opportunities",
                "error_message",
            ]
            if column in dataset.variations.columns
        ]
        sort_columns = [
            column
            for column in [
                "database_file",
                "expansion_run_id",
                "position",
            ]
            if column in variation_columns
        ]
        variation_frame = dataset.variations[
            variation_columns
        ]
        if sort_columns:
            variation_frame = variation_frame.sort_values(
                sort_columns
            )
        st.dataframe(
            variation_frame,
            use_container_width=True,
            hide_index=True,
            height=600,
            column_config={
                "query": st.column_config.TextColumn(
                    "Consulta executada",
                    width="large",
                ),
                "error_message": st.column_config.TextColumn(
                    "Erro",
                    width="large",
                ),
            },
        )

with executions_tab:
    st.subheader("Saúde das variações")
    st.caption(
        "Esta área mantém o histórico técnico; a página inicial mostra "
        "somente o ciclo mais recente."
    )
    if dataset.variations.empty:
        st.info(
            "Nenhuma execução de variação disponível."
        )
    else:
        statuses = (
            dataset.variations.assign(
                status=dataset.variations[
                    "status"
                ].fillna("UNKNOWN")
            )
            .groupby("status")
            .size()
            .sort_values(ascending=False)
            .rename("variações")
            .reset_index()
        )
        st.altair_chart(
            horizontal_count_chart(
                statuses,
                "status",
                "variações",
            ),
            use_container_width=True,
        )

        error_frame = dataset.variations.copy()
        if "error_message" in error_frame:
            error_frame = error_frame[
                error_frame["error_message"]
                .astype("string")
                .fillna("")
                .astype(str)
                .str.strip()
                .ne("")
            ]
        if not error_frame.empty:
            st.subheader("Falhas registradas")
            columns = [
                column
                for column in [
                    "database_file",
                    "query",
                    "status",
                    "pipeline_status",
                    "attempt_count",
                    "error_message",
                ]
                if column in error_frame.columns
            ]
            st.dataframe(
                error_frame[columns],
                use_container_width=True,
                hide_index=True,
            )

    st.subheader("Histórico do pipeline principal")
    if dataset.collection_runs.empty:
        st.info(
            "Nenhuma tabela collection_runs foi encontrada."
        )
    else:
        st.dataframe(
            dataset.collection_runs,
            use_container_width=True,
            hide_index=True,
            height=500,
        )

with technical_tab:
    st.subheader("Área técnica")
    st.caption(
        "Arquivos SQLite, sincronizações e tabelas carregadas. "
        "Esta seção não interfere nos filtros de negócio."
    )
    st.markdown(
        f'<p class="technical-caption">'
        f'Diretório de dados: <code>{DATA_DIR}</code>'
        "</p>",
        unsafe_allow_html=True,
    )

    st.subheader("Bancos de coleta")
    st.dataframe(
        dataset.databases,
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Sincronizações por fonte")
    if dataset.source_sync_runs.empty:
        st.info(
            "Nenhuma tabela source_sync_runs foi encontrada."
        )
    else:
        st.dataframe(
            dataset.source_sync_runs,
            use_container_width=True,
            hide_index=True,
            height=420,
        )

    st.subheader("Banco de curadoria")
    st.code(str(CURATION_DB))

    st.subheader("Inventário de tabelas")
    if dataset.inventory.empty:
        st.info("Nenhuma tabela encontrada.")
    else:
        st.dataframe(
            dataset.inventory,
            use_container_width=True,
            hide_index=True,
            height=600,
        )
