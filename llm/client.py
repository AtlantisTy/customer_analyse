from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config.model_config import get_llm
from config.settings import get_settings
from schemas.input_data import RawApiRecord
from schemas.result import AnalysisResult


def _load_prompt_template() -> ChatPromptTemplate:
    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "customer_analysis_prompt.txt"
    template_str = prompt_path.read_text(encoding="utf-8")
    # Prompt 文件使用 {{ var }} 占位符，且包含 JSON 大括号，需用 jinja2 渲染避免被当作 f-string 变量
    return ChatPromptTemplate.from_template(template_str, template_format="jinja2")


def _build_data_description(records: list[RawApiRecord]) -> str:
    return f"共有 {len(records)} 条客户记录，每条包含客户基本信息、消费金额、城市、标签等字段。"


def _compact_records_for_llm(records: list[RawApiRecord], *, topn: int) -> list[dict[str, Any]]:
    """
    降低 tokens：不传订单明细/长时间列表，仅传关键聚合指标 + 小型时间分布 + Top 产品。
    默认只传金额 TopN 客户（其余客户对“找大客户/下单时间/成交率”贡献较小）。
    """
    sorted_records = sorted(records, key=lambda r: r.total_payable_amount, reverse=True)
    selected = sorted_records[: max(1, topn)]

    out: list[dict[str, Any]] = []
    for r in selected:
        out.append(
            {
                "customer_id": r.customer_id,
                "customer_name": r.customer_name,
                "total_order_count": r.total_order_count,
                "paid_order_count": r.paid_order_count,
                "conversion_rate": r.conversion_rate,
                "total_payable_amount": r.total_payable_amount,
                "total_paid_amount": r.total_paid_amount,
                "avg_payable_amount": r.avg_payable_amount,
                "first_order_time": r.first_order_time,
                "last_order_time": r.last_order_time,
                "order_hour_histogram": r.order_hour_histogram,
                "top_products": r.top_products[:5],
            }
        )
    return out


def _strip_markdown_json_fence(text: str) -> str:
    """Remove ``` / ```json fences; many models wrap JSON despite instructions."""
    s = text.strip()
    if not s.startswith("```"):
        return s
    s = s[3:]
    if s.lower().startswith("json"):
        s = s[4:]
    s = s.lstrip()
    close = s.rfind("```")
    if close != -1:
        s = s[:close].rstrip()
    return s.strip()


def _parse_json_object_from_llm(raw: str) -> dict[str, Any]:
    """Parse JSON from LLM output; tolerate markdown fences and trailing junk."""
    text = _strip_markdown_json_fence(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # First JSON object in string (handles leading prose)
    m = re.search(r"\{", text)
    if not m:
        raise json.JSONDecodeError("No JSON object found", text, 0)

    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text[m.start() :])
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    raise json.JSONDecodeError("Could not parse JSON object", text, 0)


def _enrich_top_customers(parsed: dict[str, Any], records: list[RawApiRecord]) -> dict[str, Any]:
    """
    LLM 可能会遗漏 top_customers_by_amount 的部分字段。
    这里用我们已有的聚合数据按 customer_id 回填，保证结构稳定可导出。
    """
    index: dict[str, RawApiRecord] = {r.customer_id: r for r in records}

    top = parsed.get("top_customers_by_amount")
    if not isinstance(top, list):
        return parsed

    enriched: list[dict[str, Any]] = []
    for item in top:
        if not isinstance(item, dict):
            continue
        cid = str(item.get("customer_id") or "")
        rec = index.get(cid)
        if rec is not None:
            # 回填缺失字段（不覆盖 LLM 已给出的）
            item.setdefault("customer_name", rec.customer_name)
            item.setdefault("total_payable_amount", rec.total_payable_amount)
            item.setdefault("total_paid_amount", rec.total_paid_amount)
            item.setdefault("total_order_count", rec.total_order_count)
            item.setdefault("paid_order_count", rec.paid_order_count)
            item.setdefault("conversion_rate", rec.conversion_rate)
        enriched.append(item)

    parsed["top_customers_by_amount"] = enriched
    return parsed


def analyse_customers_with_llm(records: list[RawApiRecord]) -> AnalysisResult:
    if not records:
        raise ValueError("没有可供分析的记录。")

    settings = get_settings()
    llm = get_llm()
    prompt = _load_prompt_template()

    chain = prompt | llm | StrOutputParser()

    # 优先做“输入压缩”以提升速度与稳定性
    compact = _compact_records_for_llm(records, topn=settings.llm_input_topn_customers)

    # 超过阈值时启用分片（map）并发调用 + reduce 汇总
    if settings.llm_chunk_enabled and len(compact) >= settings.llm_chunk_threshold_customers:
        chunk_size = max(5, settings.llm_chunk_size_customers)
        chunks = [compact[i : i + chunk_size] for i in range(0, len(compact), chunk_size)]

        partials: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=max(1, settings.llm_chunk_concurrency)) as ex:
            futures = []
            for idx, ch in enumerate(chunks):
                payload = {
                    "data_description": _build_data_description(records)
                    + f"\n当前为分片分析：第 {idx+1}/{len(chunks)} 片，仅包含部分客户。",
                    "data_json": json.dumps(ch, ensure_ascii=False),
                }
                futures.append(ex.submit(chain.invoke, payload))

            for fut in as_completed(futures):
                raw = fut.result()
                parsed = _parse_json_object_from_llm(raw)
                partials.append(parsed)

        # reduce：把所有分片产出的 top_customers/insights/suggestions 合并，再让模型做一次最终汇总
        merged_top: dict[str, dict[str, Any]] = {}
        merged_insights: list[dict[str, Any]] = []
        merged_suggestions: list[str] = []
        for p in partials:
            for c in p.get("top_customers_by_amount", []) or []:
                if isinstance(c, dict) and c.get("customer_id"):
                    merged_top[str(c["customer_id"])] = c
            for ins in p.get("insights", []) or []:
                if isinstance(ins, dict):
                    merged_insights.append(ins)
            for s in p.get("suggestions", []) or []:
                if isinstance(s, str):
                    merged_suggestions.append(s)

        reduce_payload = {
            "data_description": "以下是多个分片的局部分析结果，请你做最终汇总并输出最终固定 JSON。",
            "data_json": json.dumps(
                {
                    "partials_count": len(partials),
                    "top_customers_candidates": list(merged_top.values()),
                    "insights_candidates": merged_insights[:50],
                    "suggestions_candidates": merged_suggestions[:50],
                },
                ensure_ascii=False,
            ),
        }
        raw_output = chain.invoke(reduce_payload)
        parsed = _parse_json_object_from_llm(raw_output)
        parsed = _enrich_top_customers(parsed, records)
        return AnalysisResult(**parsed)

    # 不分片：单次调用
    payload = {
        "data_description": _build_data_description(records)
        + f"\n说明：为提升速度，本次仅提供金额 Top{len(compact)} 客户的关键聚合指标。",
        "data_json": json.dumps(compact, ensure_ascii=False),
    }

    raw_output: str = chain.invoke(payload)

    try:
        parsed = _parse_json_object_from_llm(raw_output)
        parsed = _enrich_top_customers(parsed, records)
    except json.JSONDecodeError as exc:
        snippet = raw_output[:800]
        raise ValueError(f"LLM 返回的 JSON 解析失败: {exc}\n原始输出片段: {snippet}") from exc

    return AnalysisResult(**parsed)

