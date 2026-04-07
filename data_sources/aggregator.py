from __future__ import annotations

from typing import Iterable

from schemas.input_data import RawApiRecord
from data_sources.base import BaseDataFetcher


class DataAggregator:
    """聚合多个数据源，并按 customer_id 合并字段。"""

    def __init__(self, fetchers: list[BaseDataFetcher]) -> None:
        self.fetchers = fetchers

    def fetch_all(self) -> list[RawApiRecord]:
        bucket: dict[str, RawApiRecord] = {}

        for fetcher in self.fetchers:
            for record in fetcher.fetch():
                cid = record.customer_id
                if not cid:
                    continue
                if cid in bucket:
                    existing = bucket[cid]
                    merged = self._merge_records(existing, record)
                    bucket[cid] = merged
                else:
                    bucket[cid] = record

        return list(bucket.values())

    @staticmethod
    def _merge_records(a: RawApiRecord, b: RawApiRecord) -> RawApiRecord:
        data_a = a.model_dump()
        data_b = b.model_dump()

        for key, value in data_b.items():
            if key == "customer_id":
                continue

            current = data_a.get(key)
            if (current is None or current == [] or current == {} or current == "") and value not in (
                None,
                [],
                {},
                "",
            ):
                data_a[key] = value

            if key == "tags" and isinstance(current, list) and isinstance(value, list):
                # tags 做并集去重
                data_a[key] = list({*current, *value})

        return RawApiRecord(**data_a)

