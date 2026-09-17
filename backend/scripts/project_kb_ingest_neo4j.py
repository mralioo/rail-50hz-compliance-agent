"""Ingest a project's Markdown corpus into Neo4j (knowledge graph:
Project -> Substation -> Document -> Section) - parallel to
kb_ingest_neo4j.py (regulations).

Two source corpora, same downstream graph (see
scripts/project_kb_ingest_opensearch.py's docstring - same idea, applied to
the graph store instead of the vector store):
- `clean` (default) - raw Docling extraction.
- `super_clean` - LLM-cleaned text + described/categorized images. Clears
  the project's old Document+Section nodes first (Section.id is positional,
  so a different heading structure could otherwise leave stale orphans) -
  see app.kb.project_neo4j_store.clear_project.

Requires the local KB evaluation stack running (`make kb-up`) and
NEO4J_ENABLED=true + NEO4J_PASSWORD set in backend/.env. Run once, or
whenever the source corpus changes:

    .venv/bin/python scripts/project_kb_ingest_neo4j.py [--project project_1]
        [--source clean|super_clean]

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
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default="project_1")
    parser.add_argument(
        "--source", choices=["clean", "super_clean"], default="clean",
        help="dataset/<source>/<project> to ingest from (default: clean)",
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.neo4j_enabled:
        sys.exit("Set NEO4J_ENABLED=true (and NEO4J_PASSWORD) in backend/.env first.")

    source_dir = REPO_ROOT / "dataset" / args.source
    if not (source_dir / args.project).exists():
        prereq = "scripts/docling_ingest.py" if args.source == "clean" else "scripts/docling_refine.py"
        sys.exit(f"No {args.source} corpus at {source_dir / args.project} — run {prereq} first.")

    count = project_neo4j_store.ingest(source_dir, args.project)
    print(f"Ingested {count} chunk(s) from dataset/{args.source}/{args.project} into Neo4j")

    hits = project_neo4j_store.find_sections("Erdungsanlage", project=args.project)
    print(f"find_sections probe -> {len(hits)} hit(s)")
    if hits:
        h = hits[0]
        print(f"  top: [{h.substation}/{h.category}] {h.doc_name} {h.heading!r} (score={h.score:.3f})")


if __name__ == "__main__":
    main()
