from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QueryVariation:
    query: str
    position: int
    is_original: bool


class QueryExpander:
    """Generate a small deterministic set of high-precision search queries."""

    CURATED_VARIATIONS: dict[str, tuple[str, ...]] = {
        "repetitive data entry": (
            "manual data entry",
            "data entry automation",
            "repetitive form filling",
            "manual record entry",
        ),
        "spreadsheet automation": (
            "Excel automation",
            "Google Sheets automation",
            "spreadsheet workflow",
            "spreadsheet data synchronization",
        ),
        "customer support automation": (
            "helpdesk automation",
            "support ticket automation",
            "customer service workflow",
            "automated customer support",
        ),
    }

    PHRASE_VARIANTS: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("repetitive", ("manual", "recurring")),
        ("data entry", ("form filling", "record entry")),
        ("spreadsheet", ("Excel", "Google Sheets")),
        ("customer support", ("helpdesk", "customer service")),
        ("automation", ("workflow", "process automation")),
    )

    def __init__(self, max_variations: int = 5) -> None:
        if max_variations < 1:
            raise ValueError("max_variations must be at least 1")
        self.max_variations = max_variations

    @staticmethod
    def normalize(query: str) -> str:
        return re.sub(r"\s+", " ", query or "").strip()

    @staticmethod
    def _identity(query: str) -> str:
        return QueryExpander.normalize(query).casefold()

    def expand(self, query: str) -> list[QueryVariation]:
        original = self.normalize(query)
        if not original:
            raise ValueError("query cannot be empty")

        candidates: list[str] = [original]
        normalized_original = original.casefold()
        candidates.extend(self.CURATED_VARIATIONS.get(normalized_original, ()))

        if len(candidates) < self.max_variations:
            for phrase, replacements in self.PHRASE_VARIANTS:
                if phrase not in normalized_original:
                    continue
                pattern = re.compile(re.escape(phrase), flags=re.IGNORECASE)
                for replacement in replacements:
                    candidates.append(pattern.sub(replacement, original, count=1))

        generic_candidates = (
            f"manual {original}",
            f"{original} automation",
            f"{original} workflow",
            f"automated {original}",
        )
        candidates.extend(generic_candidates)

        unique_queries: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            normalized_candidate = self.normalize(candidate)
            identity = self._identity(normalized_candidate)
            if not normalized_candidate or identity in seen:
                continue
            seen.add(identity)
            unique_queries.append(normalized_candidate)
            if len(unique_queries) >= self.max_variations:
                break

        return [
            QueryVariation(
                query=value,
                position=index,
                is_original=index == 0,
            )
            for index, value in enumerate(unique_queries)
        ]
