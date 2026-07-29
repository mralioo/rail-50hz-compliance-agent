"""Central runtime configuration.

Everything is overridable via environment variables or a `.env` file so the
same codebase runs locally (mock agent, no GCP) and on Cloud Run (Vertex AI).
"""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]

_OPTIONAL_PATH_FIELDS = (
    "oda_converter_path", "dwg2dxf_path", "dxf2dwg_path",
    "dotnet_path", "acadsharp_cli_path", "qcadcmd_path",
    "node_path", "cad_viewer_cli_path",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    agent_mode: Literal["mock", "openai", "vertex"] = "mock"

    gcp_project: str | None = None
    vertex_location: str = "europe-west3"
    vertex_model: str = "gemini-2.5-flash"

    oda_converter_path: Path | None = None
    dwg2dxf_path: Path | None = None
    dxf2dwg_path: Path | None = None

    dotnet_path: Path | None = None  # for the ACadSharp engine (tools/acadsharp_cli)
    acadsharp_cli_path: Path | None = None

    qcadcmd_path: Path | None = None  # for the QCAD engine (tools/qcad_connector), DXF-only

    node_path: Path | None = None  # for cad-viewer export (tools/cad_viewer_cli)
    cad_viewer_cli_path: Path | None = None

    @field_validator(*_OPTIONAL_PATH_FIELDS, mode="before")
    @classmethod
    def _blank_env_path_to_none(cls, v: object) -> object:
        # .env.example lists these as `VAR=` (present but empty) so users have
        # a line to fill in. Pydantic coerces "" to Path("") == Path(".") -
        # truthy and .exists() (it's cwd) - so every find_*() helper below
        # would silently "find" the working directory as the binary instead
        # of correctly treating it as unset. Blank/whitespace-only -> None.
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

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
