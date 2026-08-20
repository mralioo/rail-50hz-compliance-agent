"""Ingest a project's clean Markdown corpus (dataset/clean/<project>/,
produced by scripts/docling_ingest.py) into Neo4j (knowledge graph:
Project -> Substation -> Document -> Section) - parallel to
kb_ingest_neo4j.py (regulations).

Requires the local KB evaluation stack running (`make kb-up`) and
NEO4J_ENABLED=true + NEO4J_PASSWORD set in backend/.env. Run once, or
whenever the clean corpus changes:

    .venv/bin/python scripts/project_kb_ingest_neo4j.py [--project project_1]

See docs/OPENSEARCH_NEO4J_EVALUATION.md.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.kb import project_neo4j_store  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="project_1")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.neo4j_enabled:
        sys.exit("Set NEO4J_ENABLED=true (and NEO4J_PASSWORD) in backend/.env first.")

    clean_dir = REPO_ROOT / "dataset" / "clean"
    if not (clean_dir / args.project).exists():
        sys.exit(f"No clean corpus at {clean_dir / args.project} — run scripts/docling_ingest.py first.")

    count = project_neo4j_store.ingest(clean_dir, args.project)
    print(f"Ingested {count} chunk(s) into Neo4j")

    hits = project_neo4j_store.find_sections("Erdungsanlage", project=args.project)
    print(f"find_sections probe -> {len(hits)} hit(s)")
    if hits:
        h = hits[0]
        print(f"  top: [{h.substation}/{h.category}] {h.doc_name} {h.heading!r} (score={h.score:.3f})")


if __name__ == "__main__":
    main()
