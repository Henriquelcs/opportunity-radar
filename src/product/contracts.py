from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KnowledgeType(str, Enum):
    DATA = "Dado coletado"
    EVIDENCE = "Evidência"
    INFERENCE = "Inferência"
    HYPOTHESIS = "Hipótese"
    ESTIMATE = "Estimativa"
    HUMAN_DECISION = "Decisão humana"


class LifecycleState(str, Enum):
    DETECTED = "detected"
    UNDER_REVIEW = "under_review"
    PAIN_CONFIRMED = "pain_confirmed"
    BUYER_IDENTIFIED = "buyer_identified"
    TEST_PLANNED = "test_planned"
    VALIDATING = "validating"
    INTEREST_CONFIRMED = "interest_confirmed"
    PRICE_TESTED = "price_tested"
    MVP_APPROVED = "mvp_approved"
    BUILDING = "building"
    FIRST_REVENUE = "first_revenue"
    SCALING = "scaling"
    PAUSED = "paused"
    DISCARDED = "discarded"


LIFECYCLE_LABELS: dict[str, str] = {
    LifecycleState.DETECTED.value: "Detectada",
    LifecycleState.UNDER_REVIEW.value: "Em análise",
    LifecycleState.PAIN_CONFIRMED.value: "Dor confirmada",
    LifecycleState.BUYER_IDENTIFIED.value: "Comprador identificado",
    LifecycleState.TEST_PLANNED.value: "Teste planejado",
    LifecycleState.VALIDATING.value: "Em validação",
    LifecycleState.INTEREST_CONFIRMED.value: "Interesse confirmado",
    LifecycleState.PRICE_TESTED.value: "Preço testado",
    LifecycleState.MVP_APPROVED.value: "MVP aprovado",
    LifecycleState.BUILDING.value: "Em construção",
    LifecycleState.FIRST_REVENUE.value: "Primeira receita",
    LifecycleState.SCALING.value: "Escala",
    LifecycleState.PAUSED.value: "Pausada",
    LifecycleState.DISCARDED.value: "Descartada",
}

LIFECYCLE_ORDER: tuple[str, ...] = tuple(LIFECYCLE_LABELS)

EVIDENCE_TYPES: dict[str, str] = {
    "public_source": "Fonte pública",
    "independent_signal": "Sinal independente",
    "contact_response": "Resposta de contato",
    "interview": "Entrevista",
    "workflow_observation": "Observação do processo",
    "offer_response": "Resposta à oferta",
    "price_test": "Teste de preço",
    "payment": "Pagamento",
    "other": "Outra evidência",
}

EVIDENCE_DIRECTIONS: dict[str, str] = {
    "supports": "Sustenta a hipótese",
    "contradicts": "Contradiz a hipótese",
    "neutral": "Neutra",
}

EVENT_TYPES: dict[str, str] = {
    "contact": "Contato realizado",
    "interview": "Entrevista realizada",
    "offer": "Oferta apresentada",
    "price_test": "Preço testado",
    "mvp_started": "MVP iniciado",
    "mvp_delivered": "MVP entregue",
    "revenue": "Receita registrada",
    "decision": "Decisão registrada",
    "time_spent": "Tempo investido",
    "cost": "Custo registrado",
}

SOLUTION_FORMATS: tuple[str, ...] = (
    "Não definido",
    "Serviço manual",
    "Automação sob medida",
    "Integração",
    "Ferramenta interna",
    "Micro-SaaS",
    "Extensão",
    "Produto digital",
)


@dataclass(frozen=True)
class ProductDefinition:
    name: str
    primary_user: str
    purpose: str
    job_to_be_done: str
    boundary: str


OFFICIAL_PRODUCT_DEFINITION = ProductDefinition(
    name="Opportunity Radar",
    primary_user="Henrique Luiz Costa da Silva",
    purpose=(
        "Sistema pessoal de descoberta, priorização, validação e execução "
        "de oportunidades de renda extra."
    ),
    job_to_be_done=(
        "Ajudar Henrique a encontrar uma dor com evidências, escolher o "
        "menor teste possível, validar interesse e preço e decidir, com "
        "rastreabilidade, se deve construir, continuar ou abandonar."
    ),
    boundary=(
        "O produto reduz incerteza e organiza decisões; não garante mercado, "
        "disposição a pagar, faturamento ou primeira receita."
    ),
)
