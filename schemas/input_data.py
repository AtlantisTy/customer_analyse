from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RawApiRecord(BaseModel):
    # 你可以按实际接口字段调整/扩展
    customer_id: str
    name: str | None = None
    gender: str | None = None
    age: int | None = None
    city: str | None = None
    total_order_amount: float | None = None
    last_order_date: str | None = None
    tags: list[str] | None = None
    extra: dict[str, Any] | None = None

