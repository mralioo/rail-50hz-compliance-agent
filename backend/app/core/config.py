"""Central runtime configuration.

Everything is overridable via environment variables or a `.env` file so the
same codebase runs locally (mock agent, no GCP) and on Cloud Run (Vertex AI).
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    agent_mode: Literal["mock", "openai", "vertex"] = "mock"

    gcp_project: str | None = None
    vertex_location: str = "europe-west3"
    vertex_model: str = "gemini-2.5-flash"

    oda_converter_path: Path | None = None
    dwg2dxf_path: Path | None = None

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_summary_model: str = "gpt-4o-mini"

    llm_api_key: str | None = None  # cognee's key (same OpenAI key)
    cognee_enabled: bool = False

    work_dir: Path = BACKEND_ROOT / "workdir"
    regulations_dir: Path = BACKEND_ROOT / "data" / "regulations"
    prompts_dir: Path = BACKEND_ROOT / "app" / "agent" / "prompts"

    cors_origins: list[str] = ["*"]


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    return settings
