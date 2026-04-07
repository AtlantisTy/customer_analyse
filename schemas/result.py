from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Insight(BaseModel):
    title: str
    detail: str
    level: Literal["high", "medium", "low"]


class AnalysisResult(BaseModel):
    summary: str
    insights: list[Insight]
    suggestions: list[str]

