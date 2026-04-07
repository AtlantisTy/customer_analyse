from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from schemas.input_data import RawApiRecord


class BaseDataFetcher(ABC):
    """抽象数据源接口，方便扩展多种 HTTP 接口。"""

    @abstractmethod
    def fetch(self) -> Iterable[RawApiRecord]:
        """Fetch raw records from this data source."""
        raise NotImplementedError

