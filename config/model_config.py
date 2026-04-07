from __future__ import annotations

from langchain_openai import ChatOpenAI

from config.settings import get_settings


def get_llm() -> ChatOpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise ValueError("Missing OPENAI_API_KEY. Please set it in environment variables (or .env).")

    return ChatOpenAI(
        api_key=settings.openai_api_key,
        model=settings.openai_model_name,
        base_url=settings.openai_base_url,
        temperature=settings.openai_temperature,
        timeout=settings.openai_timeout_s,
        max_retries=settings.openai_max_retries,
    )

