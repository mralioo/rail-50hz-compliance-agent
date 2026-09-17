"""Ingest the regulation corpus into OpenSearch (semantic/vector index).

Requires the local KB evaluation stack running (`make kb-up`) and
OPENSEARCH_ENABLED=true in backend/.env. Run once, or whenever the corpus
changes:

    .venv/bin/python scripts/kb_ingest_opensearch.py

See docs/OPENSEARCH_NEO4J_EVALUATION.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.rag import list_knowledge_bases  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.kb import opensearch_store  # noqa: E402


def main() -> None:
    settings = get_settings()
    if not settings.opensearch_enabled:
        sys.exit("Set OPENSEARCH_ENABLED=true in backend/.env first.")

    for kb in list_knowledge_bases():
        print(f"KB {kb.id!r} ({kb.name}) — {kb.doc_count} file(s) on disk")

    count = opensearch_store.ingest()
    print(f"\nIndexed {count} chunk(s) into {settings.opensearch_index!r}")

    hits = opensearch_store.query("minimum cable bending radius")
    print(f"query probe -> {len(hits)} hit(s)")
    if hits:
        print(f"  top: [{hits[0].doc_name}] {hits[0].heading!r} (score={hits[0].score:.3f})")


if __name__ == "__main__":
    main()
