from __future__ import annotations

import os
from functools import lru_cache

from pydantic import BaseModel, Field


class Settings(BaseModel):
    # OpenAI
    openai_api_key: str = Field(default="")
    openai_model_name: str = Field(default="gpt-4.1-mini")
    openai_base_url: str = Field(default="")
    openai_temperature: float = Field(default=0.1)
    openai_timeout_s: int = Field(default=180)
    openai_max_retries: int = Field(default=2)

    # Data sources
    api_a_base_url: str = Field(default="")
    api_a_token: str = Field(default="")
    api_b_base_url: str = Field(default="")

    # Pipeline
    output_excel_path: str = Field(default="output/customer_analysis_result.xlsx")


@lru_cache()
def get_settings() -> Settings:
    """
    Settings are loaded from environment variables.
    Optionally supports a local .env file via python-dotenv (if present).
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        # dotenv is optional; ignore if unavailable
        pass

    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4.1-mini"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
        openai_temperature=float(os.getenv("OPENAI_TEMPERATURE", "0.1")),
        openai_timeout_s=int(os.getenv("OPENAI_TIMEOUT_S", "180")),
        openai_max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "2")),
        api_a_base_url=os.getenv("API_A_BASE_URL", ""),
        api_a_token=os.getenv("API_A_TOKEN", ""),
        api_b_base_url=os.getenv("API_B_BASE_URL", ""),
        output_excel_path=os.getenv("OUTPUT_EXCEL_PATH", "output/customer_analysis_result.xlsx"),
    )

