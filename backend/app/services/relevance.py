from __future__ import annotations

import re
from dataclasses import dataclass


def _norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class RelevanceResult:
    score: float
    matched_fields: list[str]
    surface_used: str


def compute_relevance(*, requested_fields: list[str], surface_text: str, surface_used: str) -> RelevanceResult:
    normalized_surface = _norm(surface_text)
    matched: list[str] = []

    for field in requested_fields:
        normalized_field = _norm(field)
        if not normalized_field:
            continue
        if normalized_field in normalized_surface:
            matched.append(field)

    denom = max(1, len([f for f in requested_fields if _norm(f)]))
    score = len(matched) / denom
    return RelevanceResult(score=score, matched_fields=matched, surface_used=surface_used)


def passes_relevance(result: RelevanceResult, *, min_score: float = 0.4) -> bool:
    return (len(result.matched_fields) >= 1) and (result.score >= min_score)
