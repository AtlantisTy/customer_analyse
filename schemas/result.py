from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class Insight(BaseModel):
    title: str
    detail: str
    level: Literal["high", "medium", "low"]


class Overview(BaseModel):
    summary: str
    time_pattern_summary: str
    conversion_summary: str


class TopCustomerByAmount(BaseModel):
    customer_id: str
    customer_name: str | None = None
    total_payable_amount: float
    total_paid_amount: float
    total_order_count: int
    paid_order_count: int
    conversion_rate: float
    order_time_insight: str
    conversion_insight: str


class AnalysisResult(BaseModel):
    overview: Overview
    top_customers_by_amount: list[TopCustomerByAmount]
    insights: list[Insight]
    suggestions: list[str]

