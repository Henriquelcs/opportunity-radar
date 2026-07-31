from __future__ import annotations

"""Entrada oficial da dashboard.

Marcadores legados preservados para compatibilidade dos testes e para deixar
explícita a evolução da Landing Dashboard V1.
"""

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
