"""Extract dataset/raw/<project>/ into clean, folder-mirrored Markdown via
Docling (Tier 1: full ML pipeline) or a fast pdftotext stub (Tier 2) - see
app.ingestion.docling_pipeline for the tiering rule, and
docs/OPENSEARCH_NEO4J_EVALUATION.md for how the output feeds the KB stores.

    cd backend && .venv/bin/python scripts/docling_ingest.py [--project project_1]
        [--force] [--limit N]

--limit N caps how many *convertible* (non-skipped) files are processed -
useful for a quick smoke test before a full run (Tier 1 costs ~15-22s/page
on CPU, measured on this corpus's real prose documents).
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.docling_pipeline import run  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="project_1")
    parser.add_argument("--force", action="store_true", help="reconvert even if output is newer")
    parser.add_argument("--limit", type=int, default=None, help="cap convertible files processed")
    args = parser.parse_args()

    raw_dir = REPO_ROOT / "dataset" / "raw"
    clean_dir = REPO_ROOT / "dataset" / "clean"
    if not (raw_dir / args.project).exists():
        sys.exit(f"No such project: {raw_dir / args.project}")

    t0 = time.time()
    manifest = run(raw_dir, clean_dir, args.project, force=args.force, limit=args.limit)
    elapsed = time.time() - t0

    by_status = {}
    by_tier = {}
    for m in manifest:
        by_status[m.status] = by_status.get(m.status, 0) + 1
        by_tier[m.tier] = by_tier.get(m.tier, 0) + 1

    print(f"{len(manifest)} file(s) in {elapsed:.1f}s")
    print("by status:", by_status)
    print("by tier (0=skipped, 1=full, 2=fast):", by_tier)
    for m in manifest:
        if m.status == "error":
            print(f"  ERROR {m.source_path}: {m.reason}")
    print(f"\nmanifest: {clean_dir / args.project / '_manifest.json'}")


if __name__ == "__main__":
    main()
