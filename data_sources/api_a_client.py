from __future__ import annotations

from typing import Iterable

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

        url = self.settings.api_a_base_url.rstrip("/") + "/customers"
        headers: dict[str, str] = {}
        if self.settings.api_a_token:
            headers["Authorization"] = f"Bearer {self.settings.api_a_token}"

        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        customers = data.get("customers", data)  # 兼容直接返回列表的情况
        for item in customers:
            yield RawApiRecord(
                customer_id=str(item.get("id") or item.get("customer_id")),
                name=item.get("name"),
                gender=item.get("gender"),
                age=item.get("age"),
                city=item.get("city"),
                total_order_amount=item.get("total_order_amount"),
                last_order_date=item.get("last_order_date"),
                tags=item.get("tags") or [],
                extra=item,
            )

