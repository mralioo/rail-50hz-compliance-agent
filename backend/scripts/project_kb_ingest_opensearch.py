"""Ingest a project's clean Markdown corpus (dataset/clean/<project>/,
produced by scripts/docling_ingest.py) into OpenSearch (semantic/vector
index, `rail50hz_project_docs`) - parallel to kb_ingest_opensearch.py
(regulations).

Requires the local KB evaluation stack running (`make kb-up`) and
OPENSEARCH_ENABLED=true in backend/.env. Run once, or whenever the clean
corpus changes:

    .venv/bin/python scripts/project_kb_ingest_opensearch.py [--project project_1]

See docs/OPENSEARCH_NEO4J_EVALUATION.md.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.kb import project_opensearch_store  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="project_1")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.opensearch_enabled:
        sys.exit("Set OPENSEARCH_ENABLED=true in backend/.env first.")

    clean_dir = REPO_ROOT / "dataset" / "clean"
    if not (clean_dir / args.project).exists():
        sys.exit(f"No clean corpus at {clean_dir / args.project} — run scripts/docling_ingest.py first.")

    count = project_opensearch_store.ingest(clean_dir, args.project)
    print(f"Indexed {count} chunk(s) into {project_opensearch_store.PROJECT_INDEX!r}")

    hits = project_opensearch_store.query("Erdungsanlage")
    print(f"query probe -> {len(hits)} hit(s)")
    if hits:
        h = hits[0]
        print(f"  top: [{h.substation}/{h.category}] {h.doc_name} {h.heading!r} (score={h.score:.3f})")


if __name__ == "__main__":
    main()
