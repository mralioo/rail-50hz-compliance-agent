"""Ingest a project's Markdown corpus into OpenSearch (semantic/vector index,
`rail50hz_project_docs`) - parallel to kb_ingest_opensearch.py (regulations).

Two source corpora, same downstream index:
- `clean` (default until the refinement layer exists for a project) -
  produced by scripts/docling_ingest.py, raw Docling extraction.
- `super_clean` - produced by scripts/docling_refine.py: LLM-cleaned text +
  described/categorized images (see docs/DOCUMENT_EXTRACTION.md's
  refinement-layer section). Re-ingesting from here after having already
  ingested from `clean` clears the project's old chunks first (chunk_ids are
  positional within a doc, so a different heading structure could otherwise
  leave stale orphans) - see app.kb.project_opensearch_store.clear_project.

Requires the local KB evaluation stack running (`make kb-up`) and
OPENSEARCH_ENABLED=true in backend/.env. Run once, or whenever the source
corpus changes:

    .venv/bin/python scripts/project_kb_ingest_opensearch.py [--project project_1]
        [--source clean|super_clean]

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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default="project_1")
    parser.add_argument(
        "--source", choices=["clean", "super_clean"], default="clean",
        help="dataset/<source>/<project> to ingest from (default: clean)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.opensearch_enabled:
        sys.exit("Set OPENSEARCH_ENABLED=true in backend/.env first.")

    source_dir = REPO_ROOT / "dataset" / args.source
    if not (source_dir / args.project).exists():
        prereq = "scripts/docling_ingest.py" if args.source == "clean" else "scripts/docling_refine.py"
        sys.exit(f"No {args.source} corpus at {source_dir / args.project} — run {prereq} first.")

    count = project_opensearch_store.ingest(source_dir, args.project)
    print(f"Indexed {count} chunk(s) from dataset/{args.source}/{args.project} into {project_opensearch_store.PROJECT_INDEX!r}")

    hits = project_opensearch_store.query("Erdungsanlage")
    print(f"query probe -> {len(hits)} hit(s)")
    if hits:
        h = hits[0]
        print(f"  top: [{h.substation}/{h.category}] {h.doc_name} {h.heading!r} (score={h.score:.3f})")


if __name__ == "__main__":
    main()
