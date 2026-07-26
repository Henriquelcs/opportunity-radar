from __future__ import annotations

import html
import re
from typing import Any


PAIN_PATTERNS: dict[str, list[str]] = {
    "manual_work": [
        r"\bmanual(?:ly)?\b",
        r"\bby hand\b",
        r"\bcopy and paste\b",
        r"\bcopy[- ]paste\b",
    ],
    "time_waste": [
        r"\bwaste(?:s|d|ing)? time\b",
        r"\btime[- ]consuming\b",
        r"\btakes? hours?\b",
        r"\bspend(?:ing)? hours?\b",
    ],
    "repetitive_work": [
        r"\brepetitive\b",
        r"\bevery day\b",
        r"\bevery week\b",
        r"\bover and over\b",
        r"\bagain and again\b",
    ],
    "frustration": [
        r"\bfrustrat(?:ed|ing|ion)\b",
        r"\bannoying\b",
        r"\bpainful\b",
        r"\btedious\b",
        r"\bhate\b",
    ],
    "missing_solution": [
        r"\bno tool\b",
        r"\bno solution\b",
        r"\bdoesn't exist\b",
        r"\bdoes not exist\b",
        r"\bwish there was\b",
        r"\blooking for a tool\b",
    ],
    "problem_report": [
        r"\bproblem\b",
        r"\bissue\b",
        r"\bstruggling\b",
        r"\bdifficult\b",
        r"\bhard to\b",
        r"\bcan't figure out\b",
        r"\bcannot figure out\b",
    ],
}


def clean_text(value: str | None) -> str:
    """
    Remove HTML simples e normaliza espaços.
    """
    if not value:
        return ""

    decoded_text = html.unescape(value)

    without_tags = re.sub(
        r"<[^>]+>",
        " ",
        decoded_text,
    )

    normalized_text = re.sub(
        r"\s+",
        " ",
        without_tags,
    )

    return normalized_text.strip().lower()


def build_item_text(item: dict[str, Any]) -> str:
    """
    Combina os campos textuais de uma publicação.
    """
    fields = [
        item.get("title"),
        item.get("text"),
        item.get("url"),
    ]

    valid_fields = [
        str(field)
        for field in fields
        if field
    ]

    return clean_text(" ".join(valid_fields))


def detect_pain_signals(
    text: str,
) -> dict[str, list[str]]:
    """
    Detecta sinais de dor em um texto.

    Retorna:
    {
        "categoria": ["expressão encontrada"]
    }
    """
    normalized_text = clean_text(text)

    detected_signals: dict[str, list[str]] = {}

    for category, patterns in PAIN_PATTERNS.items():
        matches: list[str] = []

        for pattern in patterns:
            result = re.search(
                pattern,
                normalized_text,
                flags=re.IGNORECASE,
            )

            if result:
                matches.append(result.group(0))

        if matches:
            detected_signals[category] = matches

    return detected_signals


def analyze_item(
    item: dict[str, Any],
) -> dict[str, Any]:
    """
    Analisa uma publicação e adiciona sinais de dor.
    """
    item_text = build_item_text(item)
    pain_signals = detect_pain_signals(item_text)

    analyzed_item = dict(item)

    analyzed_item["analyzed_text"] = item_text
    analyzed_item["pain_signals"] = pain_signals
    analyzed_item["pain_categories"] = list(
        pain_signals.keys()
    )
    analyzed_item["has_pain_signal"] = bool(
        pain_signals
    )

    return analyzed_item


def filter_items_with_pain(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Retorna apenas publicações com sinais de dor.
    """
    analyzed_items = [
        analyze_item(item)
        for item in items
    ]

    return [
        item
        for item in analyzed_items
        if item["has_pain_signal"]
    ]
