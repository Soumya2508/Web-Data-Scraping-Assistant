from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class DecisionTraceEntry(BaseModel):
    step: str
    ok: bool = True
    ms: Optional[int] = None
    details: Optional[dict[str, Any]] = None


class AnalyzeResponse(BaseModel):
    mode_used: Literal["document", "xhr", "selenium"]
    has_data: bool
    message: str
    csv_url: Optional[str] = None
    record_count: int = 0
    decision_trace: list[DecisionTraceEntry] = Field(default_factory=list)
