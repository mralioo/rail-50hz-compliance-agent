"""Ingest the regulation corpus into Neo4j (knowledge graph).

Requires the local KB evaluation stack running (`make kb-up`) and
NEO4J_ENABLED=true + NEO4J_PASSWORD set in backend/.env (must match
docker-compose.kb.yml's NEO4J_AUTH). Run once, or whenever the corpus
changes:

    .venv/bin/python scripts/kb_ingest_neo4j.py

See docs/OPENSEARCH_NEO4J_EVALUATION.md.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent.rag import list_knowledge_bases  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.kb import neo4j_store  # noqa: E402


def main() -> None:
    settings = get_settings()
    if not settings.neo4j_enabled:
        sys.exit("Set NEO4J_ENABLED=true (and NEO4J_PASSWORD) in backend/.env first.")

    for kb in list_knowledge_bases():
        print(f"KB {kb.id!r} ({kb.name}) — {kb.doc_count} file(s) on disk")

    count = neo4j_store.ingest()
    print(f"\nIngested {count} chunk(s) into Neo4j")

    status = neo4j_store.code_status("Ril 954.0107")
    print(f"code_status probe -> {status}")


if __name__ == "__main__":
    main()
