from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass(slots=True)
class Opportunity:
    """
    Representa uma oportunidade identificada pelo radar.
    """

    id: str
    source: str
    title: str
    description: str
    url: str

    author: str | None = None
    published_at: str | None = None

    pain_categories: list[str] = field(
        default_factory=list
    )

    pain_signals: dict[str, list[str]] = field(
        default_factory=dict
    )

    engagement_score: float = 0.0
    pain_score: float = 0.0
    urgency_score: float = 0.0
    market_score: float = 0.0
    confidence_score: float = 0.0
    opportunity_score: float = 0.0

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        """
        Converte a oportunidade para dicionário.
        """
        return asdict(self)
