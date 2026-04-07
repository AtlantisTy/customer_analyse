from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from config.model_config import get_llm
from schemas.input_data import RawApiRecord
from schemas.result import AnalysisResult


def _load_prompt_template() -> ChatPromptTemplate:
    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "customer_analysis_prompt.txt"
    template_str = prompt_path.read_text(encoding="utf-8")
    # Prompt 文件使用 {{ var }} 占位符，且包含 JSON 大括号，需用 jinja2 渲染避免被当作 f-string 变量
    return ChatPromptTemplate.from_template(template_str, template_format="jinja2")


def _build_data_description(records: list[RawApiRecord]) -> str:
    return f"共有 {len(records)} 条客户记录，每条包含客户基本信息、消费金额、城市、标签等字段。"


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

    llm = get_llm()
    prompt = _load_prompt_template()

    chain = prompt | llm | StrOutputParser()

    payload = {
        "data_description": _build_data_description(records),
        "data_json": json.dumps([r.model_dump() for r in records], ensure_ascii=False),
    }

    raw_output: str = chain.invoke(payload)

    try:
        parsed = _parse_json_object_from_llm(raw_output)
        parsed = _enrich_top_customers(parsed, records)
    except json.JSONDecodeError as exc:
        snippet = raw_output[:800]
        raise ValueError(f"LLM 返回的 JSON 解析失败: {exc}\n原始输出片段: {snippet}") from exc

    return AnalysisResult(**parsed)

