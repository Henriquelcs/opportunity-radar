from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_v2_preserves_runner_and_business_areas() -> None:
    app = (ROOT / "src/dashboard/product_app.py").read_text(encoding="utf-8")
    assert "Da dor pública à <span>próxima decisão.</span>" in app
    assert "Score de descoberta ≠ mercado" in app
    assert '"Início"' in app
    assert '"Decisão"' in app
    assert '"Validação"' in app
    assert '"Oportunidades"' in app
    assert '"Curadoria"' in app
    assert '"Métricas"' in app
    assert '"Consultas"' in app
    assert '"Execuções"' in app
    assert '"Área técnica"' in app
    assert "Runner V2 preservado" in app


def test_product_documentation_contract_exists() -> None:
    required = {
        "docs/product_definition.md",
        "docs/user_and_jobs.md",
        "docs/scoring_model.md",
        "docs/opportunity_quality.md",
        "docs/opportunity_lifecycle.md",
        "docs/monetization_framework.md",
        "docs/personal_fit_model.md",
        "docs/translation_strategy.md",
        "docs/validation_playbook.md",
        "docs/mvp_plan_contract.md",
        "docs/glossary.md",
        "docs/data_contract.md",
        "docs/product_metrics.md",
        "docs/risks_and_limitations.md",
        "docs/roadmap.md",
        "docs/examples/end_to_end_opportunity.md",
    }
    missing = sorted(path for path in required if not (ROOT / path).is_file())
    assert missing == []


def test_readme_states_product_boundary() -> None:
    content = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "sistema pessoal de descoberta, priorização, validação e execução" in content
    assert "Score de descoberta" in content
    assert "não garante" in content
    assert "python scripts/run_colab.py --mode all" in content


def test_decision_card_buttons_have_stable_unique_keys() -> None:
    app = (ROOT / "src/dashboard/product_app.py").read_text(encoding="utf-8")
    assert "def _render_decision_card(row: pd.Series, *, widget_scope: str)" in app
    assert 'key=f"view_now_{widget_scope}_{opportunity_key}"' in app
    assert 'key=f"work_now_{widget_scope}_{opportunity_key}"' in app
    assert '_render_decision_card(selected, widget_scope="home")' in app
    assert '_render_decision_card(row, widget_scope="decision")' in app


def test_opportunity_browser_opens_title_and_details() -> None:
    app = (ROOT / "src/dashboard/product_app.py").read_text(encoding="utf-8")
    assert "def _render_opportunity_browser(" in app
    assert "def _render_opportunity_detail(" in app
    assert 'key=f"title_open_{widget_scope}_{key}"' in app
    assert 'key=f"view_open_{widget_scope}_{key}"' in app
    assert '"Ver oportunidade"' in app
    assert '"Abrir publicação original"' in app
    assert '"Trabalhar nesta oportunidade"' in app
    assert "Conteúdo original preservado" in app
    assert 'widget_scope="opportunities"' in app


def test_visual_finish_hides_legacy_copy_and_identifies_build() -> None:
    entrypoint = (ROOT / "src/dashboard/app.py").read_text(encoding="utf-8")
    app = (ROOT / "src/dashboard/product_app.py").read_text(encoding="utf-8")
    assert not entrypoint.lstrip().startswith('"""')
    assert "Marcadores legados preservados" not in entrypoint
    assert 'APP_VERSION = "2.1.0"' in app
    assert "Product System V{APP_VERSION}" in app
    assert "use_container_width=True" not in app
