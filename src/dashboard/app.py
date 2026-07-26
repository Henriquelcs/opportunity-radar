from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_DIR = Path(__file__).resolve().parents[2]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from src.dashboard.data_access import discover_databases, load_radar_data


st.set_page_config(
    page_title="Opportunity Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {padding-top: 1.35rem; padding-bottom: 3rem;}
        [data-testid="stMetric"] {
            border: 1px solid rgba(120, 120, 120, 0.20);
            border-radius: 14px;
            padding: 14px 16px;
            background: rgba(120, 120, 120, 0.04);
        }
        .radar-subtitle {color: #7c8594; margin-top: -0.6rem;}
        .status-ok {font-weight: 700; color: #22a06b;}
        .status-warn {font-weight: 700; color: #d97706;}
        div[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

DATA_DIR = Path(
    os.getenv("OPPORTUNITY_RADAR_DATA_DIR", str(PROJECT_DIR / "data"))
).resolve()


@st.cache_data(ttl=20, show_spinner=False)
def cached_load(data_dir: str, selected_files: tuple[str, ...]):
    return load_radar_data(data_dir, selected_files)


def unique_nonempty(series: pd.Series) -> list[str]:
    values = {
        str(value).strip()
        for value in series.fillna("").tolist()
        if str(value).strip()
    }
    return sorted(values, key=str.casefold)


def status_rate(frame: pd.DataFrame) -> tuple[int, int]:
    if frame.empty or "status" not in frame.columns:
        return 0, 0
    statuses = frame["status"].fillna("").astype(str).str.upper()
    return int(statuses.eq("SUCCESS").sum()), int(len(statuses))


def consolidate_global(opportunities: pd.DataFrame) -> pd.DataFrame:
    if opportunities.empty:
        return opportunities.copy()
    result = opportunities.copy()
    result["score_sort"] = pd.to_numeric(result["score"], errors="coerce")
    result["has_query"] = result["original_queries"].fillna("").astype(str).ne("")
    result = result.sort_values(
        ["has_query", "score_sort", "match_count"],
        ascending=[False, False, False],
        na_position="last",
    )
    url_key = result["url"].fillna("").astype(str).str.strip()
    title_key = result["title"].fillna("").astype(str).str.casefold().str.strip()
    result["global_key"] = url_key.mask(url_key.eq(""), title_key)
    result = result.drop_duplicates("global_key", keep="first")
    return result.drop(columns=["score_sort", "has_query", "global_key"])


def render_table(frame: pd.DataFrame, height: int = 520) -> None:
    if frame.empty:
        st.info("Nenhum registro disponível para os filtros selecionados.")
        return
    visible_columns = [
        column
        for column in [
            "title",
            "source",
            "score",
            "level",
            "original_queries",
            "matched_queries",
            "match_count",
            "pain_categories",
            "database_file",
            "url",
        ]
        if column in frame.columns
    ]
    display = frame[visible_columns].copy()
    if "score" in display:
        display["score"] = pd.to_numeric(display["score"], errors="coerce").round(2)
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=height,
        column_config={
            "title": st.column_config.TextColumn("Oportunidade", width="large"),
            "source": st.column_config.TextColumn("Fonte", width="small"),
            "score": st.column_config.NumberColumn("Score", format="%.2f"),
            "level": st.column_config.TextColumn("Nível", width="small"),
            "original_queries": st.column_config.TextColumn(
                "Consulta original", width="medium"
            ),
            "matched_queries": st.column_config.TextColumn(
                "Variação encontrada", width="medium"
            ),
            "match_count": st.column_config.NumberColumn("Matches", format="%d"),
            "pain_categories": st.column_config.TextColumn("Dores", width="medium"),
            "database_file": st.column_config.TextColumn("Banco", width="medium"),
            "url": st.column_config.LinkColumn("Abrir", display_text="Abrir fonte"),
        },
    )


st.title("📡 Opportunity Radar")
st.markdown(
    '<p class="radar-subtitle">Dores públicas → oportunidades SaaS → dados reais consolidados</p>',
    unsafe_allow_html=True,
)

available_paths = discover_databases(DATA_DIR)
available_files = [path.name for path in available_paths]

with st.sidebar:
    st.header("Controles")
    st.caption(f"Dados: `{DATA_DIR}`")
    selected_files = st.multiselect(
        "Bancos SQLite",
        available_files,
        default=available_files,
        help="Selecione um ou mais bancos gerados pelas coletas.",
    )
    if st.button("Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("Filtros das oportunidades")

if not available_files:
    st.error(
        "Nenhum banco SQLite foi encontrado na pasta data. "
        "Execute primeiro uma coleta real do Opportunity Radar."
    )
    st.stop()

if not selected_files:
    st.warning("Selecione pelo menos um banco SQLite na barra lateral.")
    st.stop()

dataset = cached_load(str(DATA_DIR), tuple(selected_files))
opportunities = dataset.opportunities.copy()
global_opportunities = consolidate_global(opportunities)

with st.sidebar:
    source_options = unique_nonempty(global_opportunities.get("source", pd.Series(dtype=str)))
    selected_sources = st.multiselect("Fontes", source_options, default=source_options)

    query_values: set[str] = set()
    if "original_queries" in global_opportunities:
        for value in global_opportunities["original_queries"].fillna(""):
            query_values.update(
                item.strip() for item in str(value).split("|") if item.strip()
            )
    selected_queries = st.multiselect(
        "Consultas originais",
        sorted(query_values, key=str.casefold),
        default=sorted(query_values, key=str.casefold),
    )

    score_values = pd.to_numeric(
        global_opportunities.get("score", pd.Series(dtype=float)),
        errors="coerce",
    ).dropna()
    max_score = float(score_values.max()) if not score_values.empty else 100.0
    minimum_score = st.slider(
        "Score mínimo",
        min_value=0.0,
        max_value=max(100.0, max_score),
        value=0.0,
        step=1.0,
    )
    search_text = st.text_input("Buscar no título", placeholder="Ex.: Excel, helpdesk...")

filtered = global_opportunities.copy()
if selected_sources and "source" in filtered:
    filtered = filtered[filtered["source"].isin(selected_sources)]
if selected_queries and "original_queries" in filtered:
    pattern = "|".join(re.escape(query) for query in selected_queries)
    filtered = filtered[
        filtered["original_queries"].fillna("").str.contains(
            pattern, case=False, regex=True
        )
    ]
if "score" in filtered:
    numeric_score = pd.to_numeric(filtered["score"], errors="coerce")
    filtered = filtered[numeric_score.isna() | numeric_score.ge(minimum_score)]
if search_text.strip() and "title" in filtered:
    filtered = filtered[
        filtered["title"].fillna("").str.contains(
            search_text.strip(), case=False, regex=False
        )
    ]

successful_runs, total_runs = status_rate(dataset.expansion_runs)
duplicate_total = 0
if not dataset.expansion_runs.empty and "duplicate_matches" in dataset.expansion_runs:
    duplicate_total = int(
        pd.to_numeric(
            dataset.expansion_runs["duplicate_matches"], errors="coerce"
        ).fillna(0).sum()
    )

metric_columns = st.columns(5)
metric_columns[0].metric("Oportunidades únicas", len(global_opportunities))
metric_columns[1].metric("Após filtros", len(filtered))
metric_columns[2].metric("Fontes", len(source_options))
metric_columns[3].metric("Expansões concluídas", f"{successful_runs}/{total_runs}")
metric_columns[4].metric("Duplicações consolidadas", duplicate_total)

if total_runs and successful_runs == total_runs:
    st.markdown(
        '<span class="status-ok">● Todas as expansões selecionadas concluíram com sucesso.</span>',
        unsafe_allow_html=True,
    )
elif total_runs:
    st.markdown(
        '<span class="status-warn">● Existem expansões incompletas ou com erro.</span>',
        unsafe_allow_html=True,
    )

overview_tab, opportunities_tab, queries_tab, executions_tab, inspector_tab = st.tabs(
    [
        "Visão geral",
        "Oportunidades",
        "Consultas e variações",
        "Execuções",
        "Dados SQLite",
    ]
)

with overview_tab:
    left, right = st.columns(2)
    with left:
        st.subheader("Oportunidades por fonte")
        if not filtered.empty and "source" in filtered:
            source_chart = (
                filtered.assign(source=filtered["source"].replace("", "não informada"))
                .groupby("source")
                .size()
                .sort_values(ascending=False)
                .rename("oportunidades")
            )
            st.bar_chart(source_chart)
        else:
            st.info("Sem dados de fonte.")

    with right:
        st.subheader("Oportunidades por consulta")
        if not dataset.matches.empty:
            query_chart = (
                dataset.matches.assign(
                    original_query=dataset.matches["original_query"].replace(
                        "", "não informada"
                    )
                )
                .groupby("original_query")["opportunity_url"]
                .nunique()
                .sort_values(ascending=False)
                .rename("oportunidades")
            )
            st.bar_chart(query_chart)
        else:
            st.info("Os bancos selecionados não possuem rastreabilidade de consulta.")

    st.subheader("Oportunidades em destaque")
    top_items = filtered.copy()
    if "score" in top_items:
        top_items["_score"] = pd.to_numeric(top_items["score"], errors="coerce")
        top_items = top_items.sort_values("_score", ascending=False, na_position="last")
        top_items = top_items.drop(columns="_score")
    render_table(top_items.head(15), height=480)

with opportunities_tab:
    st.subheader("Oportunidades consolidadas")
    st.caption(
        "Uma URL aparece uma única vez nesta visão. As variações que encontraram "
        "o mesmo item permanecem registradas nas colunas de consulta."
    )
    render_table(filtered, height=650)

with queries_tab:
    st.subheader("Execuções de expansão")
    if dataset.expansion_runs.empty:
        st.info("Nenhum histórico de expansão encontrado nos bancos selecionados.")
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
        st.dataframe(
            dataset.variations[variation_columns].sort_values(
                [c for c in ["database_file", "expansion_run_id", "position"] if c in variation_columns]
            ),
            use_container_width=True,
            hide_index=True,
            height=560,
        )

with executions_tab:
    st.subheader("Saúde das variações")
    if dataset.variations.empty:
        st.info("Nenhuma execução de variação disponível.")
    else:
        statuses = (
            dataset.variations.assign(
                status=dataset.variations["status"].fillna("UNKNOWN")
            )
            .groupby("status")
            .size()
            .sort_values(ascending=False)
            .rename("variações")
        )
        st.bar_chart(statuses)

        error_frame = dataset.variations.copy()
        if "error_message" in error_frame:
            error_frame = error_frame[
                error_frame["error_message"].fillna("").astype(str).str.strip().ne("")
            ]
        if not error_frame.empty:
            st.subheader("Falhas registradas")
            columns = [
                c
                for c in [
                    "database_file",
                    "query",
                    "status",
                    "pipeline_status",
                    "attempt_count",
                    "error_message",
                ]
                if c in error_frame.columns
            ]
            st.dataframe(
                error_frame[columns],
                use_container_width=True,
                hide_index=True,
            )

    st.subheader("Histórico do pipeline principal")
    if dataset.collection_runs.empty:
        st.info("Nenhuma tabela collection_runs foi encontrada.")
    else:
        st.dataframe(
            dataset.collection_runs,
            use_container_width=True,
            hide_index=True,
            height=480,
        )

with inspector_tab:
    st.subheader("Bancos carregados")
    st.dataframe(
        dataset.databases,
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("Inventário de tabelas")
    if dataset.inventory.empty:
        st.info("Nenhuma tabela encontrada.")
    else:
        st.dataframe(
            dataset.inventory,
            use_container_width=True,
            hide_index=True,
            height=560,
        )
