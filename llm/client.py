from __future__ import annotations

import json
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
    return ChatPromptTemplate.from_template(template_str)


def _build_data_description(records: list[RawApiRecord]) -> str:
    return f"共有 {len(records)} 条客户记录，每条包含客户基本信息、消费金额、城市、标签等字段。"


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
        parsed: dict[str, Any] = json.loads(raw_output)
    except json.JSONDecodeError as exc:
        snippet = raw_output[:500]
        raise ValueError(f"LLM 返回的 JSON 解析失败: {exc}\n原始输出片段: {snippet}") from exc

    return AnalysisResult(**parsed)

