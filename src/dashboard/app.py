from __future__ import annotations

import hashlib
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


st.set_page_config(
    page_title="Opportunity Radar",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        .block-container {padding-top: 1.2rem; padding-bottom: 3rem;}
        [data-testid="stMetric"] {
            border: 1px solid rgba(120, 120, 120, 0.20);
            border-radius: 14px;
            padding: 14px 16px;
            background: rgba(120, 120, 120, 0.04);
        }
        .radar-subtitle {color: #7c8594; margin-top: -0.6rem;}
        .status-ok {font-weight: 700; color: #22a06b;}
        .status-warn {font-weight: 700; color: #d97706;}
        .technical-caption {color: #7c8594; font-size: 0.9rem;}
        div[data-testid="stDataFrame"] {border-radius: 12px; overflow: hidden;}
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] code {
            white-space: normal;
            word-break: break-all;
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


def status_rate(frame: pd.DataFrame) -> tuple[int, int]:
    if frame.empty or "status" not in frame.columns:
        return 0, 0
    statuses = frame["status"].astype("string").fillna("").astype(str).str.upper()
    return int(statuses.eq("SUCCESS").sum()), int(len(statuses))


def consolidate_global(opportunities: pd.DataFrame) -> pd.DataFrame:
    if opportunities.empty:
        return opportunities.copy()

    result = opportunities.copy()
    result["score_sort"] = pd.to_numeric(result["score"], errors="coerce")
    result["has_query"] = (
        result["original_queries"].astype("string").fillna("").astype(str).ne("")
    )
    result = result.sort_values(
        ["has_query", "score_sort", "match_count"],
        ascending=[False, False, False],
        na_position="last",
    )
    url_key = result["url"].astype("string").fillna("").astype(str).str.strip()
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
    return result.drop(columns=["score_sort", "has_query", "global_key"])


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
            "curation_label": st.column_config.TextColumn(
                "Curadoria", width="medium"
            ),
            "original_queries": st.column_config.TextColumn(
                "Consulta original", width="large"
            ),
            "matched_queries": st.column_config.TextColumn(
                "Variação encontrada", width="large"
            ),
            "match_count": st.column_config.NumberColumn("Matches", format="%d"),
            "pain_categories": st.column_config.TextColumn(
                "Sinais de dor", width="large"
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
        .mark_bar(cornerRadiusEnd=4)
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
                alt.Tooltip(f"{value_column}:Q", title="Oportunidades"),
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
        for value in filtered_opportunities.get("url", pd.Series(dtype=str))
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
                records.append({"consulta": normalized, "url": url})

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
        return pd.DataFrame(columns=["curadoria", "oportunidades"])
    return (
        frame.groupby("curation_label")
        .size()
        .sort_values(ascending=False)
        .rename("oportunidades")
        .reset_index()
        .rename(columns={"curation_label": "curadoria"})
    )


st.title("📡 Radar de Oportunidades")
st.markdown(
    '<p class="radar-subtitle">'
    "Dores públicas → oportunidades de solução com IA → potencial de renda extra"
    "</p>",
    unsafe_allow_html=True,
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
dataset = cached_load(str(DATA_DIR), tuple(available_files))
curation_mtime = CURATION_DB.stat().st_mtime_ns
curation = cached_load_curation(str(CURATION_DB), curation_mtime)

global_opportunities = attach_curation(
    consolidate_global(dataset.opportunities.copy()),
    curation,
)

with st.sidebar:
    st.header("Filtros")
    if st.button("Atualizar dados", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    source_options = unique_nonempty(
        global_opportunities.get("source", pd.Series(dtype=str))
    )
    selected_sources = st.multiselect(
        "Fontes",
        source_options,
        default=source_options,
    )

    query_values: set[str] = set()
    if "original_queries" in global_opportunities:
        for value in global_opportunities["original_queries"].astype(
            "string"
        ).fillna(""):
            query_values.update(
                item.strip() for item in str(value).split("|") if item.strip()
            )
    query_options = sorted(query_values, key=str.casefold)
    selected_queries = st.multiselect(
        "Consultas originais",
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
    search_text = st.text_input(
        "Buscar no título",
        placeholder="Ex.: planilha, suporte, relatório",
    )

    st.divider()
    st.caption(
        f"{len(available_files)} bancos de coleta carregados. "
        "Detalhes técnicos estão na aba Área técnica."
    )

filtered = global_opportunities.copy()

if selected_sources and "source" in filtered:
    filtered = filtered[filtered["source"].isin(selected_sources)]
if selected_queries and "original_queries" in filtered:
    pattern = "|".join(re.escape(query) for query in selected_queries)
    filtered = filtered[
        filtered["original_queries"]
        .astype("string")
        .fillna("")
        .astype(str)
        .str.contains(pattern, case=False, regex=True)
    ]
if selected_status_labels and "curation_label" in filtered:
    filtered = filtered[filtered["curation_label"].isin(selected_status_labels)]
if "score" in filtered:
    numeric_score = pd.to_numeric(filtered["score"], errors="coerce")
    filtered = filtered[numeric_score.isna() | numeric_score.ge(minimum_score)]
if search_text.strip() and "title" in filtered:
    filtered = filtered[
        filtered["title"]
        .astype("string")
        .fillna("")
        .astype(str)
        .str.contains(search_text.strip(), case=False, regex=False)
    ]

successful_runs, total_runs = status_rate(dataset.expansion_runs)
duplicate_total = 0
if not dataset.expansion_runs.empty and "duplicate_matches" in dataset.expansion_runs:
    duplicate_total = int(
        pd.to_numeric(
            dataset.expansion_runs["duplicate_matches"], errors="coerce"
        ).fillna(0).sum()
    )

filtered_source_count = (
    filtered["source"].replace("", pd.NA).dropna().nunique()
    if not filtered.empty and "source" in filtered
    else 0
)

metric_columns = st.columns(5)
metric_columns[0].metric("Oportunidades exibidas", len(filtered))
metric_columns[1].metric("Total consolidado", len(global_opportunities))
metric_columns[2].metric("Fontes exibidas", int(filtered_source_count))
metric_columns[3].metric(
    "Expansões concluídas",
    f"{successful_runs}/{total_runs}",
)
metric_columns[4].metric("Duplicações removidas", duplicate_total)

if total_runs and successful_runs == total_runs:
    st.markdown(
        '<span class="status-ok">'
        "● Todas as expansões registradas concluíram com sucesso."
        "</span>",
        unsafe_allow_html=True,
    )
elif total_runs:
    st.markdown(
        '<span class="status-warn">'
        "● Existem expansões incompletas ou com erro."
        "</span>",
        unsafe_allow_html=True,
    )

(
    overview_tab,
    opportunities_tab,
    curation_tab,
    queries_tab,
    executions_tab,
    technical_tab,
) = st.tabs(
    [
        "Visão geral",
        "Oportunidades",
        "Detalhes e curadoria",
        "Consultas e variações",
        "Execuções",
        "Área técnica",
    ]
)

with overview_tab:
    left, right = st.columns(2)

    with left:
        st.subheader("Oportunidades por fonte")
        if not filtered.empty and "source" in filtered:
            source_counts = (
                filtered.assign(
                    source=filtered["source"].replace("", "Não informada")
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
            st.info("Sem dados de fonte para os filtros selecionados.")

    with right:
        st.subheader("Oportunidades por consulta")
        query_counts = query_counts_for_filtered(filtered, dataset.matches)
        if query_counts.empty:
            st.info("Sem rastreabilidade de consulta para os filtros selecionados.")
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
    top_items = filtered.copy()
    if "score" in top_items:
        top_items["_score"] = pd.to_numeric(top_items["score"], errors="coerce")
        top_items = top_items.sort_values(
            "_score",
            ascending=False,
            na_position="last",
        ).drop(columns="_score")
    render_table(top_items.head(15), height=520)

with opportunities_tab:
    st.subheader("Oportunidades consolidadas")
    st.caption(
        "Os números, gráficos e esta tabela respeitam os filtros da barra lateral. "
        "Uma URL aparece apenas uma vez."
    )
    render_table(filtered, height=700)

with curation_tab:
    st.subheader("Detalhes e curadoria")
    reviewable = filtered[
        filtered.get("url", pd.Series(index=filtered.index, dtype=str))
        .astype("string")
        .fillna("")
        .astype(str)
        .str.strip()
        .ne("")
    ].copy()

    if reviewable.empty:
        st.info("Nenhuma oportunidade com URL está disponível para revisão.")
    else:
        reviewable["_score"] = pd.to_numeric(
            reviewable.get("score", pd.Series(index=reviewable.index, dtype=float)),
            errors="coerce",
        )
        reviewable = reviewable.sort_values(
            ["_score", "title"],
            ascending=[False, True],
            na_position="last",
        ).drop(columns="_score")

        title_by_url = {
            str(row["url"]): str(row.get("title", "") or row["url"])
            for _, row in reviewable.iterrows()
        }
        selected_url = st.selectbox(
            "Selecione uma oportunidade",
            options=list(title_by_url),
            format_func=lambda value: title_by_url[value],
        )
        selected_row = reviewable[reviewable["url"].eq(selected_url)].iloc[0]

        with st.container(border=True):
            st.markdown(f"### {selected_row.get('title', 'Sem título')}")
            detail_columns = st.columns(4)
            detail_columns[0].metric(
                "Fonte",
                str(selected_row.get("source", "") or "Não informada"),
            )
            score_value = pd.to_numeric(
                pd.Series([selected_row.get("score")]),
                errors="coerce",
            ).iloc[0]
            detail_columns[1].metric(
                "Score",
                "—" if pd.isna(score_value) else f"{float(score_value):.2f}",
            )
            detail_columns[2].metric(
                "Nível",
                str(selected_row.get("level", "") or "Não informado"),
            )
            detail_columns[3].metric(
                "Matches",
                int(selected_row.get("match_count", 0) or 0),
            )

            st.markdown(f"**Consulta original:** {selected_row.get('original_queries', '') or 'Não informada'}")
            st.markdown(f"**Variação encontrada:** {selected_row.get('matched_queries', '') or 'Não informada'}")
            st.markdown(f"**Sinais de dor:** {selected_row.get('pain_categories', '') or 'Não informados'}")
            st.link_button(
                "Abrir oportunidade na fonte pública",
                selected_url,
                use_container_width=True,
            )

        current_status = str(
            selected_row.get("curation_status", "unreviewed") or "unreviewed"
        )
        current_label = CURATION_LABELS.get(
            current_status,
            CURATION_LABELS["unreviewed"],
        )
        status_label = st.radio(
            "Classificação",
            options=list(CURATION_LABELS.values()),
            index=list(CURATION_LABELS.values()).index(current_label),
            horizontal=True,
        )
        note_key = hashlib.sha1(selected_url.encode("utf-8")).hexdigest()[:12]
        notes = st.text_area(
            "Observações",
            value=str(selected_row.get("curation_notes", "") or ""),
            placeholder=(
                "Registre por que esta dor é válida, precisa de revisão "
                "ou é um falso positivo."
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
            st.toast("Classificação salva.")
            st.rerun()

with queries_tab:
    st.subheader("Execuções de expansão")
    if dataset.expansion_runs.empty:
        st.info("Nenhum histórico de expansão encontrado.")
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
        variation_frame = dataset.variations[variation_columns]
        if sort_columns:
            variation_frame = variation_frame.sort_values(sort_columns)
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
            .reset_index()
        )
        st.altair_chart(
            horizontal_count_chart(statuses, "status", "variações"),
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
        st.info("Nenhuma tabela collection_runs foi encontrada.")
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
        "Esta seção mostra os arquivos SQLite e as tabelas carregadas. "
        "Ela não interfere nos filtros de negócio."
    )
    st.markdown(
        f'<p class="technical-caption">Diretório de dados: <code>{DATA_DIR}</code></p>',
        unsafe_allow_html=True,
    )
    st.subheader("Bancos de coleta")
    st.dataframe(
        dataset.databases,
        use_container_width=True,
        hide_index=True,
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
