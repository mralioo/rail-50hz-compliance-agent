"""Cognee memory bridge — guideline/norm knowledge for the agents.

Guidelines and norms are ingested once (`scripts/seed_memory.py`) into
cognee's local stores (SQLite/LanceDB/Kuzu). Agents call `recall()` to pull
the top-k most relevant snippets into their prompts — deliberately selective
(k=2, 400 chars each) so memory refines answers without flooding the prompt.

Best-effort by design: disabled (`COGNEE_ENABLED=false`), unseeded, or
timed-out memory silently yields [] and the agents fall back to the local
regulation corpus (`agent/rag.py`).
"""
import asyncio
import os

from app.core.config import get_settings

RECALL_TIMEOUT_S = 30  # cognee recall is LLM-routed; 10 s proved too tight
SNIPPET_CHARS = 400


def _prepare_env() -> bool:
    settings = get_settings()
    if not settings.cognee_enabled:
        return False
    if settings.llm_api_key:
        os.environ.setdefault("LLM_API_KEY", settings.llm_api_key)
    return True


def recall(query: str, k: int = 2) -> list[str]:
    """Top-k guideline snippets for the query; [] on any failure."""
    if not _prepare_env():
        return []
    try:
        import cognee  # deferred: heavy import

        async def _recall():
            return await cognee.recall(query_text=query)

        results = asyncio.run(asyncio.wait_for(_recall(), timeout=RECALL_TIMEOUT_S))
        return [str(getattr(r, "text", r))[:SNIPPET_CHARS] for r in results[:k]]
    except Exception:
        return []


def remember(text: str) -> bool:
    """Ingest one guideline/norm document into memory."""
    if not _prepare_env():
        return False
    try:
        import cognee

        async def _remember():
            await cognee.remember(text)

        asyncio.run(_remember())
        return True
    except Exception:
        return False
