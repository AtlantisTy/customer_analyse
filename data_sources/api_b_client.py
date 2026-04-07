from __future__ import annotations

from typing import Iterable

import requests

from config.settings import get_settings
from data_sources.base import BaseDataFetcher
from schemas.input_data import RawApiRecord


class ApiBClient(BaseDataFetcher):
    """
    示例：补充客户行为/标签等信息的接口。
    这里假设返回结构中至少包含 id / customer_id 与 tags。
    """

    def __init__(self) -> None:
        self.settings = get_settings()

    def fetch(self) -> Iterable[RawApiRecord]:
        if not self.settings.api_b_base_url:
            # B 接口可选，如果没配，则直接返回空迭代器
            return []

        url = self.settings.api_b_base_url.rstrip("/") + "/customer_activity"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        activities = data.get("activities", data)
        for item in activities:
            yield RawApiRecord(
                customer_id=str(item.get("id") or item.get("customer_id")),
                tags=item.get("tags") or [],
                extra=item,
            )

