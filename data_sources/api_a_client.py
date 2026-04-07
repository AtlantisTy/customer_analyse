from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Iterable, Any

import requests

from config.settings import get_settings
from data_sources.base import BaseDataFetcher
from schemas.input_data import RawApiRecord


class ApiAClient(BaseDataFetcher):
    """
    示例：主业务接口，获取客户基础与订单信息。
    真实项目中，请根据实际接口返回结构调整字段映射。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def fetch(self) -> Iterable[RawApiRecord]:
        if not self.settings.api_a_base_url:
            raise ValueError("API_A_BASE_URL 未配置，请在环境变量或 .env 中设置。")

        # 订单列表接口（按你的描述：response.data.list）
        url = self.settings.api_a_base_url
        headers: dict[str, str] = {}
        if self.settings.api_a_token:
            headers["Authorization"] = f"{self.settings.api_a_token}"
        data = {
            "page": 1,
            "pageSize": 10,
        }

        resp = requests.post(url, headers=headers, json=data,timeout=10)
        resp.raise_for_status()
        data = resp.json()

        orders = _deep_get(data, ["data", "list"], default=None)
        if orders is None:
            # 兼容：有些接口直接返回 list
            orders = data if isinstance(data, list) else data.get("list", [])

        by_customer: dict[str, dict[str, Any]] = {}

        for o in orders:
            cid = str(o.get("customerId") or o.get("customer_id") or "")
            if not cid:
                continue

            cust = by_customer.setdefault(
                cid,
                {
                    "customer_id": cid,
                    "customer_name": o.get("customerName"),
                    "total_order_count": 0,
                    "paid_order_count": 0,
                    "total_payable_amount": 0.0,
                    "total_paid_amount": 0.0,
                    "order_create_times": [],
                    "order_hour_histogram": Counter(),
                    "product_counter": Counter(),
                    "extra_orders_sample": [],
                },
            )

            cust["total_order_count"] += 1

            payable = _to_float(o.get("payableAmount"))
            paid = _to_float(o.get("paidAmount"))
            cust["total_payable_amount"] += payable
            cust["total_paid_amount"] += paid

            # 成交判断：优先 payStatusName == 已付款 或 payStatus == 3
            pay_status = o.get("payStatus")
            pay_status_name = o.get("payStatusName")
            is_paid = (pay_status == 3) or (str(pay_status_name) == "已付款") or (paid > 0)
            if is_paid:
                cust["paid_order_count"] += 1

            ct = o.get("createTime")
            if ct:
                cust["order_create_times"].append(str(ct))
                hour = _parse_hour(str(ct))
                if hour is not None:
                    cust["order_hour_histogram"][f"{hour:02d}"] += 1

            for p in (o.get("orderProductResponseList") or []):
                name = p.get("productName")
                if name:
                    cust["product_counter"][str(name)] += 1

            # 保留少量原始订单，方便追溯（避免太大）
            if len(cust["extra_orders_sample"]) < 3:
                cust["extra_orders_sample"].append(o)

        for cid, c in by_customer.items():
            total_orders = int(c["total_order_count"])
            paid_orders = int(c["paid_order_count"])
            total_payable_amount = float(c["total_payable_amount"])
            total_paid_amount = float(c["total_paid_amount"])
            conversion_rate = (paid_orders / total_orders) if total_orders else 0.0
            avg_payable_amount = (total_payable_amount / total_orders) if total_orders else 0.0

            times = c["order_create_times"]
            first_time, last_time = _min_max_time_str(times)

            top_products = [
                {"product_name": k, "count": v}
                for k, v in c["product_counter"].most_common(10)
            ]

            yield RawApiRecord(
                customer_id=cid,
                customer_name=c.get("customer_name"),
                total_order_count=total_orders,
                paid_order_count=paid_orders,
                conversion_rate=conversion_rate,
                total_payable_amount=total_payable_amount,
                total_paid_amount=total_paid_amount,
                avg_payable_amount=avg_payable_amount,
                first_order_time=first_time,
                last_order_time=last_time,
                order_create_times=times,
                order_hour_histogram=dict(c["order_hour_histogram"]),
                top_products=top_products,
                extra={"orders_sample": c["extra_orders_sample"]},
            )


def _deep_get(data: Any, path: list[str], default: Any = None) -> Any:
    cur = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except Exception:
        return 0.0


def _parse_hour(dt_str: str) -> int | None:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(dt_str, fmt).hour
        except Exception:
            continue
    return None


def _min_max_time_str(times: list[str]) -> tuple[str | None, str | None]:
    parsed: list[datetime] = []
    for t in times:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
            try:
                parsed.append(datetime.strptime(t, fmt))
                break
            except Exception:
                continue
    if not parsed:
        return None, None
    return min(parsed).strftime("%Y-%m-%d %H:%M:%S"), max(parsed).strftime("%Y-%m-%d %H:%M:%S")

