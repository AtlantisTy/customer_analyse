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

    df_overview = pd.DataFrame(
        [
            {
                "summary": result.overview.summary,
                "time_pattern_summary": result.overview.time_pattern_summary,
                "conversion_summary": result.overview.conversion_summary,
            }
        ]
    )
    df_top_customers = pd.DataFrame(
        [
            {
                "customer_id": c.customer_id,
                "customer_name": c.customer_name,
                "total_payable_amount": c.total_payable_amount,
                "total_paid_amount": c.total_paid_amount,
                "total_order_count": c.total_order_count,
                "paid_order_count": c.paid_order_count,
                "conversion_rate": c.conversion_rate,
                "order_time_insight": c.order_time_insight,
                "conversion_insight": c.conversion_insight,
            }
            for c in result.top_customers_by_amount
        ]
    )
    df_insights = pd.DataFrame(
        [{"title": ins.title, "detail": ins.detail, "level": ins.level} for ins in result.insights]
    )
    df_suggestions = pd.DataFrame([{"suggestion": s} for s in result.suggestions])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_overview.to_excel(writer, sheet_name="overview", index=False)
        df_top_customers.to_excel(writer, sheet_name="top_customers", index=False)
        df_insights.to_excel(writer, sheet_name="insights", index=False)
        df_suggestions.to_excel(writer, sheet_name="suggestions", index=False)


def run_customer_analysis() -> None:
    settings = get_settings()

    fetchers = [ApiAClient(), ApiBClient()]
    aggregator = DataAggregator(fetchers=fetchers)

    print("开始获取并聚合订单数据...")
    records = aggregator.fetch_all()
    if not records:
        print("未获取到任何客户数据，流程结束。")
        return
    print(f"聚合完成：{len(records)} 个客户行为记录。")

    print("开始调用大模型进行分析...")
    result = analyse_customers_with_llm(records)
    print("大模型分析完成，开始导出 Excel...")

    output_path = Path(settings.output_excel_path)
    _export_to_excel(result, output_path)

    print(f"分析完成，结果已导出到: {output_path.resolve()}")

