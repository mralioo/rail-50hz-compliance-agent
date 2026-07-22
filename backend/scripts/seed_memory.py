"""Seed the Cognee memory with the guideline/norm corpus.

Ingests every markdown file under data/regulations/ (and optionally
data/norms/ for additional DB/VDE material). Run once, or whenever the
corpus changes:

    COGNEE_ENABLED=true .venv/bin/python scripts/seed_memory.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.memory import cognee_store  # noqa: E402


def main() -> None:
    settings = get_settings()
    if not settings.cognee_enabled:
        sys.exit("Set COGNEE_ENABLED=true (and LLM_API_KEY) in backend/.env first.")

    sources = [settings.regulations_dir, settings.regulations_dir.parent / "norms"]
    files = [p for src in sources if src.exists() for p in sorted(src.glob("*.md"))]
    if not files:
        sys.exit("No guideline files found to ingest.")

    for path in files:
        ok = cognee_store.remember(f"[{path.name}]\n{path.read_text(encoding='utf-8')}")
        print(f"{'OK  ' if ok else 'FAIL'} {path}")

    probe = cognee_store.recall("minimum cable bending radius")
    print(f"\nrecall probe -> {len(probe)} snippet(s)")
    if probe:
        print(probe[0][:160])


if __name__ == "__main__":
    main()
