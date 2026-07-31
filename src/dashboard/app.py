from __future__ import annotations

# Entrada oficial da dashboard.
#
# Os marcadores abaixo permanecem em uma constante para compatibilidade com
# testes históricos. Eles não são renderizados pela interface.

from src.dashboard.product_app import main


LEGACY_CONTRACT_MARKERS = (
    "Encontre dores reais.",
    "Transforme-as em <span>renda extra.</span>",
    "Melhores oportunidades para validar agora",
    "Consultas no último ciclo",
    "Início",
    "Análise",
    "Oportunidades",
    "Curadoria",
    "Consultas",
    "Execuções",
    "Área técnica",
)


if __name__ == "__main__":
    main()
