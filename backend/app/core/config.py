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
    "node_path", "cad_viewer_cli_path", "freecadcmd_path",
    "freecad_gui_path", "xpra_path",
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

    freecadcmd_path: Path | None = None  # Craftsman agent (tools/freecad_worker), 2D geometry ops

    # Craftsman "live" mode - the real FreeCAD GUI streamed into the browser
    # via xpra's HTML5 client, so ops execute against one persistent
    # document instead of a fresh one-shot subprocess per call. Optional,
    # separate from freecadcmd_path above (a GUI-capable build + xpra, not
    # just FreeCADCmd) - degrades to "not configured" if unset, same
    # pattern as freecadcmd_path. See tools/freecad_worker/live_env/ and
    # docs/CRAFTSMAN_AGENT.md.
    freecad_gui_path: Path | None = None
    xpra_path: Path | None = None
    craftsman_live_op_port: int = 8765
    craftsman_live_html_port: int = 8766
    craftsman_live_display: str = ":100"

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

    # --- Docling document-extraction service (dataset/raw -> clean Markdown +
    # image artifacts; see app.application.documents). Runs the ML pipeline on
    # a remote server so there is no local CPU cost. ---
    docling_base_url: str = "http://10.0.1.236/docling"
    docling_chunk_max_tokens: int = 512
    docling_images_scale: float = 2.0
    embedding_model: str = "intfloat/multilingual-e5-large"

    # --- Refinement layer (dataset/clean -> dataset/super_clean; see
    # app.application.documents.refine_pipeline). LLM-based OCR/repetition
    # cleanup + image description/categorization, same remote server as
    # Docling/embeddings, nginx-proxied at /generative/. ---
    vllm_generative_base_url: str = "http://10.0.1.236/generative"
    generative_model: str = "google/gemma-4-31B-it"

    cors_origins: list[str] = ["*"]

    # --- OpenSearch / Neo4j KB evaluation (local Docker only; see
    # docs/OPENSEARCH_NEO4J_EVALUATION.md). Not consumed by rag.py/routes.py
    # yet — these back the standalone backend/app/kb/ evaluation harness.
    opensearch_enabled: bool = False
    opensearch_host: str = "http://localhost:9200"
    opensearch_index: str = "rail50hz_regulations"
    opensearch_embedding_provider: Literal["local", "openai", "vllm"] = "local"
    # "vllm" calls the remote embedding model (same one Docling/ITUKI use) over
    # the network instead of loading a local model — no torch/API-key needed,
    # but requires network access to this URL. Proxied via nginx the same way
    # docling_base_url is (see app/adapters/documents/docling_client.py).
    vllm_embeddings_base_url: str = "http://10.0.1.236/embeddings"

    neo4j_enabled: bool = False
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str | None = None


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.work_dir.mkdir(parents=True, exist_ok=True)
    return settings
