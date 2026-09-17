"""Hybrid fusion PoC CLI: query both OpenSearch and Neo4j, merge the
results, and print the annotated answer plus a timing table.

    .venv/bin/python scripts/kb_compare.py "minimum cable bending radius"
    .venv/bin/python scripts/kb_compare.py "Ril 954.0107" --kb general

See docs/OPENSEARCH_NEO4J_EVALUATION.md. Standalone script — not wired into
routes.py/`/chat`.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.kb import fusion  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--kb", action="append", dest="kb_ids", help="repeatable: --kb general --kb db")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args()

    settings = get_settings()
    if not (settings.opensearch_enabled and settings.neo4j_enabled):
        sys.exit("Set both OPENSEARCH_ENABLED=true and NEO4J_ENABLED=true in backend/.env first.")

    result = fusion.compare(args.query, k=args.k, kb_ids=args.kb_ids)

    print(f"query: {result.query!r}  (kb={args.kb_ids or 'all'})\n")
    print(f"semantic hits: {len(result.semantic_hits)}  fulltext hits: {len(result.fulltext_hits)}"
          f"  codes checked: {len(result.graph_context)}\n")
    for line in result.merged:
        print(f"- {line}\n")
    print("timings (ms):", result.timings)


if __name__ == "__main__":
    main()
