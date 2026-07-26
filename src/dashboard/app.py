from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[2]

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(
        0,
        str(ROOT_DIR),
    )


import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.service import (
    LEVEL_LABELS,
)
from src.dashboard.service import (
    build_average_scores_by_source,
)
from src.dashboard.service import (
    build_level_distribution,
)
from src.dashboard.service import (
    build_opportunity_table,
)
from src.dashboard.service import (
    build_runs_history,
)
from src.dashboard.service import (
    build_score_breakdown,
)
from src.dashboard.service import (
    build_source_distribution,
)
from src.dashboard.service import (
    calculate_summary,
)
from src.dashboard.service import (
    filter_opportunities,
)
from src.dashboard.service import (
    format_datetime,
)
from src.dashboard.service import (
    normalize_level,
)
from src.storage.database import (
    DEFAULT_DATABASE_PATH,
)
from src.storage.opportunity_repository import (
    CollectionRunRepository,
)
from src.storage.opportunity_repository import (
    OpportunityRepository,
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
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }

        [data-testid="stMetricValue"] {
            font-size: 1.75rem;
        }

        .opportunity-card {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 12px;
            padding: 18px;
            margin-bottom: 14px;
        }

        .score-badge {
            font-size: 1.1rem;
            font-weight: 700;
        }

        .card-title {
            font-size: 1.15rem;
            font-weight: 700;
            margin-top: 4px;
            margin-bottom: 8px;
        }

        .small-muted {
            opacity: 0.72;
            font-size: 0.9rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def resolve_database_path() -> Path:
    """
    Resolve o banco configurado para o dashboard.
    """
    environment_path = os.getenv(
        "OPPORTUNITY_RADAR_DATABASE",
        "",
    ).strip()

    if environment_path:
        return Path(environment_path)

    return ROOT_DIR / DEFAULT_DATABASE_PATH


@st.cache_resource
def get_repositories(
    database_path: str,
):
    """
    Inicializa repositórios compartilhados.
    """
    opportunity_repository = (
        OpportunityRepository(
            database_path
        )
    )

    run_repository = (
        CollectionRunRepository(
            database_path
        )
    )

    return (
        opportunity_repository,
        run_repository,
    )


@st.cache_data(ttl=30)
def load_dashboard_data(
    database_path: str,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    """
    Carrega oportunidades e execuções.
    """
    (
        opportunity_repository,
        run_repository,
    ) = get_repositories(
        database_path
    )

    opportunities = (
        opportunity_repository.list_ranked(
            limit=10000,
            minimum_score=0.0,
        )
    )

    runs = run_repository.list_recent(
        limit=100
    )

    return opportunities, runs


def render_header(
    database_path: Path,
) -> None:
    """
    Renderiza o cabeçalho do produto.
    """
    title_column, action_column = (
        st.columns(
            [5, 1]
        )
    )

    with title_column:
        st.title(
            "📡 Opportunity Radar"
        )

        st.caption(
            "Descoberta, análise e priorização "
            "de oportunidades de produto."
        )

    with action_column:
        st.write("")

        if st.button(
            "Atualizar dados",
            use_container_width=True,
        ):
            load_dashboard_data.clear()
            st.rerun()

    st.caption(
        f"Banco: `{database_path}`"
    )


def render_empty_state() -> None:
    """
    Exibe estado vazio.
    """
    st.info(
        "Nenhuma oportunidade foi armazenada ainda."
    )

    st.code(
        (
            'python main.py '
            '--query "workflow automation" '
            '--limit 20'
        ),
        language="bash",
    )


def render_metrics(
    summary: dict[str, Any],
) -> None:
    """
    Exibe KPIs principais.
    """
    columns = st.columns(5)

    columns[0].metric(
        "Oportunidades",
        summary[
            "total_opportunities"
        ],
    )

    columns[1].metric(
        "Score médio",
        f"{summary['average_score']:.1f}",
    )

    columns[2].metric(
        "Alto potencial",
        summary[
            "high_potential_count"
        ],
    )

    columns[3].metric(
        "Fontes ativas",
        summary[
            "source_count"
        ],
    )

    columns[4].metric(
        "Última execução",
        summary[
            "last_run_status"
        ],
        help=(
            format_datetime(
                summary[
                    "last_run_at"
                ]
            )
        ),
    )


def render_overview_charts(
    opportunities: list[
        dict[str, Any]
    ],
) -> None:
    """
    Exibe gráficos executivos.
    """
    source_data = pd.DataFrame(
        build_source_distribution(
            opportunities
        )
    )

    level_data = pd.DataFrame(
        build_level_distribution(
            opportunities
        )
    )

    average_source_data = pd.DataFrame(
        build_average_scores_by_source(
            opportunities
        )
    )

    score_data = pd.DataFrame(
        build_score_breakdown(
            opportunities
        )
    )

    first_column, second_column = (
        st.columns(2)
    )

    with first_column:
        st.subheader(
            "Oportunidades por fonte"
        )

        if not source_data.empty:
            figure = px.bar(
                source_data,
                x="source",
                y="count",
                labels={
                    "source": "Fonte",
                    "count": (
                        "Oportunidades"
                    ),
                },
            )

            figure.update_layout(
                showlegend=False,
            )

            st.plotly_chart(
                figure,
                use_container_width=True,
            )

    with second_column:
        st.subheader(
            "Classificação de potencial"
        )

        if not level_data.empty:
            figure = px.pie(
                level_data,
                names="label",
                values="count",
                hole=0.5,
            )

            st.plotly_chart(
                figure,
                use_container_width=True,
            )

    third_column, fourth_column = (
        st.columns(2)
    )

    with third_column:
        st.subheader(
            "Score médio por fonte"
        )

        if not average_source_data.empty:
            figure = px.bar(
                average_source_data,
                x="source",
                y="average_score",
                labels={
                    "source": "Fonte",
                    "average_score": (
                        "Score médio"
                    ),
                },
            )

            figure.update_yaxes(
                range=[0, 100]
            )

            figure.update_layout(
                showlegend=False,
            )

            st.plotly_chart(
                figure,
                use_container_width=True,
            )

    with fourth_column:
        st.subheader(
            "Dimensões do score"
        )

        if not score_data.empty:
            figure = px.bar(
                score_data,
                x="dimension",
                y="average_score",
                labels={
                    "dimension": (
                        "Dimensão"
                    ),
                    "average_score": (
                        "Score médio"
                    ),
                },
            )

            figure.update_yaxes(
                range=[0, 100]
            )

            figure.update_layout(
                showlegend=False,
            )

            st.plotly_chart(
                figure,
                use_container_width=True,
            )


def render_filters(
    opportunities: list[
        dict[str, Any]
    ],
) -> dict[str, Any]:
    """
    Renderiza filtros laterais.
    """
    st.sidebar.header(
        "Filtros"
    )

    available_sources = sorted(
        {
            str(
                item.get("source")
                or "unknown"
            )
            for item in opportunities
        }
    )

    available_levels = [
        level
        for level in LEVEL_LABELS
        if any(
            normalize_level(
                item.get(
                    "opportunity_level"
                )
            )
            == level
            for item in opportunities
        )
    ]

    selected_sources = (
        st.sidebar.multiselect(
            "Fontes",
            options=available_sources,
            default=available_sources,
        )
    )

    selected_level_labels = (
        st.sidebar.multiselect(
            "Níveis",
            options=[
                LEVEL_LABELS[level]
                for level in available_levels
            ],
            default=[
                LEVEL_LABELS[level]
                for level in available_levels
            ],
        )
    )

    selected_levels = [
        level
        for level, label in (
            LEVEL_LABELS.items()
        )
        if label in selected_level_labels
    ]

    minimum_score = (
        st.sidebar.slider(
            "Score mínimo",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
        )
    )

    search_text = (
        st.sidebar.text_input(
            "Buscar",
            placeholder=(
                "Título, descrição ou dor"
            ),
        )
    )

    maximum_results = (
        st.sidebar.selectbox(
            "Máximo de resultados",
            options=[
                25,
                50,
                100,
                250,
                500,
            ],
            index=1,
        )
    )

    return {
        "sources": selected_sources,
        "levels": selected_levels,
        "minimum_score": (
            minimum_score
        ),
        "search_text": search_text,
        "maximum_results": (
            maximum_results
        ),
    }


def render_opportunity_cards(
    opportunities: list[
        dict[str, Any]
    ],
) -> None:
    """
    Exibe cards detalhados.
    """
    st.subheader(
        "Oportunidades prioritárias"
    )

    if not opportunities:
        st.warning(
            "Nenhuma oportunidade corresponde "
            "aos filtros selecionados."
        )
        return

    for position, item in enumerate(
        opportunities,
        start=1,
    ):
        score = float(
            item.get(
                "opportunity_score",
                0,
            )
            or 0
        )

        level = normalize_level(
            item.get(
                "opportunity_level"
            )
        )

        title = str(
            item.get("title")
            or "Sem título"
        )

        source = str(
            item.get("source")
            or "unknown"
        )

        description = str(
            item.get("description")
            or ""
        )

        url = str(
            item.get("url")
            or ""
        )

        categories = item.get(
            "pain_categories",
            [],
        ) or []

        with st.container(
            border=True
        ):
            header_column, score_column = (
                st.columns(
                    [5, 1]
                )
            )

            with header_column:
                st.markdown(
                    f"### {position}. {title}"
                )

                st.caption(
                    f"Fonte: {source} · "
                    f"Nível: "
                    f"{LEVEL_LABELS[level]} · "
                    f"Última captura: "
                    f"{format_datetime(item.get('last_seen_at'))}"
                )

            with score_column:
                st.metric(
                    "Score",
                    f"{score:.1f}",
                )

            if description:
                st.write(
                    description[:600]
                )

            if categories:
                st.caption(
                    "Dores identificadas: "
                    + ", ".join(
                        categories
                    )
                )

            score_columns = st.columns(5)

            score_columns[0].metric(
                "Dor",
                f"{float(item.get('pain_score', 0) or 0):.1f}",
            )

            score_columns[1].metric(
                "Urgência",
                f"{float(item.get('urgency_score', 0) or 0):.1f}",
            )

            score_columns[2].metric(
                "Engajamento",
                f"{float(item.get('engagement_score', 0) or 0):.1f}",
            )

            score_columns[3].metric(
                "Mercado",
                f"{float(item.get('market_score', 0) or 0):.1f}",
            )

            score_columns[4].metric(
                "Confiança",
                f"{float(item.get('confidence_score', 0) or 0):.1f}",
            )

            if url:
                st.link_button(
                    "Abrir publicação original",
                    url,
                )


def render_opportunity_table(
    opportunities: list[
        dict[str, Any]
    ],
) -> None:
    """
    Exibe tabela completa.
    """
    st.subheader(
        "Tabela consolidada"
    )

    table = pd.DataFrame(
        build_opportunity_table(
            opportunities
        )
    )

    if table.empty:
        st.info(
            "Nenhum registro para exibição."
        )
        return

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Score": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Dor": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Urgência": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Engajamento": (
                st.column_config.NumberColumn(
                    format="%.1f",
                )
            ),
            "Mercado": st.column_config.NumberColumn(
                format="%.1f",
            ),
            "Confiança": (
                st.column_config.NumberColumn(
                    format="%.1f",
                )
            ),
            "URL": st.column_config.LinkColumn(
                display_text="Abrir",
            ),
        },
    )


def render_run_history(
    runs: list[dict[str, Any]],
) -> None:
    """
    Exibe histórico das execuções.
    """
    st.subheader(
        "Histórico de execuções"
    )

    history = build_runs_history(
        runs
    )

    if not history:
        st.info(
            "Nenhuma execução registrada."
        )
        return

    history_frame = pd.DataFrame(
        history
    )

    chart_frame = history_frame.copy()

    chart_frame = chart_frame.sort_values(
        by="started_at",
        ascending=True,
    )

    figure = px.line(
        chart_frame,
        x="started_at_label",
        y=[
            "collected",
            "pain",
            "opportunities",
            "persisted",
        ],
        markers=True,
        labels={
            "started_at_label": (
                "Execução"
            ),
            "value": "Quantidade",
            "variable": "Métrica",
        },
    )

    st.plotly_chart(
        figure,
        use_container_width=True,
    )

    display_columns = [
        "id",
        "started_at_label",
        "status",
        "query",
        "collected",
        "pain",
        "opportunities",
        "persisted",
        "errors",
    ]

    st.dataframe(
        history_frame[
            display_columns
        ],
        use_container_width=True,
        hide_index=True,
    )


def main() -> None:
    database_path = (
        resolve_database_path()
    )

    render_header(
        database_path
    )

    try:
        opportunities, runs = (
            load_dashboard_data(
                str(database_path)
            )
        )

    except Exception as error:
        st.error(
            "Falha ao carregar o banco de dados."
        )

        st.exception(error)
        return

    if not opportunities:
        render_empty_state()

        if runs:
            render_run_history(runs)

        return

    summary = calculate_summary(
        opportunities,
        runs,
    )

    render_metrics(summary)

    filters = render_filters(
        opportunities
    )

    filtered_opportunities = (
        filter_opportunities(
            opportunities=opportunities,
            sources=filters[
                "sources"
            ],
            levels=filters[
                "levels"
            ],
            minimum_score=filters[
                "minimum_score"
            ],
            search_text=filters[
                "search_text"
            ],
        )
    )

    filtered_opportunities = (
        filtered_opportunities[
            :filters[
                "maximum_results"
            ]
        ]
    )

    tabs = st.tabs(
        [
            "Visão executiva",
            "Ranking",
            "Tabela",
            "Execuções",
        ]
    )

    with tabs[0]:
        render_overview_charts(
            filtered_opportunities
        )

    with tabs[1]:
        render_opportunity_cards(
            filtered_opportunities
        )

    with tabs[2]:
        render_opportunity_table(
            filtered_opportunities
        )

    with tabs[3]:
        render_run_history(runs)


if __name__ == "__main__":
    main()
