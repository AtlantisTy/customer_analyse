from __future__ import annotations

from pathlib import Path

import pandas as pd

from config.settings import get_settings
from data_sources.aggregator import DataAggregator
from data_sources.api_a_client import ApiAClient
from data_sources.api_b_client import ApiBClient
from llm.client import analyse_customers_with_llm
from schemas.result import AnalysisResult


def _export_to_excel(result: AnalysisResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_summary = pd.DataFrame([{"summary": result.summary}])
    df_insights = pd.DataFrame(
        [{"title": ins.title, "detail": ins.detail, "level": ins.level} for ins in result.insights]
    )
    df_suggestions = pd.DataFrame([{"suggestion": s} for s in result.suggestions])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="summary", index=False)
        df_insights.to_excel(writer, sheet_name="insights", index=False)
        df_suggestions.to_excel(writer, sheet_name="suggestions", index=False)


def run_customer_analysis() -> None:
    settings = get_settings()

    fetchers = [ApiAClient(), ApiBClient()]
    aggregator = DataAggregator(fetchers=fetchers)

    records = aggregator.fetch_all()
    if not records:
        print("未获取到任何客户数据，流程结束。")
        return

    result = analyse_customers_with_llm(records)

    output_path = Path(settings.output_excel_path)
    _export_to_excel(result, output_path)

    print(f"分析完成，结果已导出到: {output_path.resolve()}")

