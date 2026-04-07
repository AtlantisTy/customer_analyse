from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RawApiRecord(BaseModel):
    """
    客户行为聚合后的记录（由“订单列表 response.data.list”计算得到）。
    这份结构会直接喂给大模型。
    """

    customer_id: str
    customer_name: str | None = None

    total_order_count: int
    paid_order_count: int
    conversion_rate: float  # 成交率 = paid_order_count / total_order_count

    total_payable_amount: float
    total_paid_amount: float
    avg_payable_amount: float

    first_order_time: str | None = None
    last_order_time: str | None = None

    # 用于分析下单时间（可以是 createTime 列表或已聚合的小时分布）
    order_create_times: list[str] = []
    order_hour_histogram: dict[str, int] = {}

    # 可选：产品偏好（来自 orderProductResponseList.productName）
    top_products: list[dict[str, Any]] = []

    extra: dict[str, Any] | None = None

