"""Refine dataset/clean/<project>/ into dataset/super_clean/<project>/: an
LLM cleans up OCR/extraction noise in the text, and describes + categorizes
each extracted image — see docs/DOCUMENT_EXTRACTION.md's refinement-layer
section. Run scripts/docling_ingest.py first (this reads its output).

    cd backend && .venv/bin/python scripts/docling_refine.py [--project project_1]
        [--force] [--limit N] [--concurrency N] [--base-url URL] [-v]

The server (VLLM_GENERATIVE_BASE_URL, default http://10.0.1.236/generative)
runs the LLM (google/gemma-4-31B-it at time of writing) - one call per
document to clean its text, one call per image to describe it.

--concurrency N: images and documents are described/cleaned via the same
shared generative server also used for chat/other services on that box —
keep this modest (default 1) unless you know the server can take more load.
--limit N caps how many documents are processed - useful for a quick check
before a full run.
-v: per-file progress logging.
"""
import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.documents.dataset_refinement_service import run_project  # noqa: E402
from app.application.documents.refine_pipeline import build_refine_pipeline  # noqa: E402
from app.bootstrap import (  # noqa: E402
    get_document_file_storage,
    get_image_description_client,
    get_text_refinement_client,
)
from app.core.config import get_settings  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default="project_1")
    parser.add_argument("--force", action="store_true", help="re-refine even if output is newer")
    parser.add_argument("--limit", type=int, default=None, help="cap documents processed")
    parser.add_argument("--concurrency", type=int, default=1, help="max documents refined in parallel (default 1)")
    parser.add_argument("--base-url", default=None, help="override VLLM_GENERATIVE_BASE_URL")
    parser.add_argument("-v", "--verbose", action="store_true", help="per-file progress logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    clean_dir = REPO_ROOT / "dataset" / "clean"
    super_clean_dir = REPO_ROOT / "dataset" / "super_clean"
    if not (clean_dir / args.project).exists():
        sys.exit(f"No clean corpus at {clean_dir / args.project} — run scripts/docling_ingest.py first.")

    settings = get_settings()
    text_refinement = get_text_refinement_client(args.base_url)
    image_description = get_image_description_client(args.base_url)
    file_storage = get_document_file_storage(super_clean_dir / args.project)
    pipeline = build_refine_pipeline(
        text_refinement, image_description, file_storage, settings.generative_model
    )

    print(
        f"refining '{args.project}' (concurrency={args.concurrency}, "
        f"force={args.force}, limit={args.limit})..."
    )
    t0 = time.time()
    manifest = asyncio.run(
        run_project(
            pipeline,
            clean_dir=clean_dir,
            super_clean_dir=super_clean_dir,
            project=args.project,
            force=args.force,
            limit=args.limit,
            concurrency=args.concurrency,
        )
    )
    elapsed = time.time() - t0

    by_status: dict[str, int] = {}
    total_images = 0
    total_described = 0
    for m in manifest:
        by_status[m.status] = by_status.get(m.status, 0) + 1
        total_images += m.image_count
        total_described += m.described_count

    print(f"\n{len(manifest)} file(s) in {elapsed:.1f}s")
    print("by status:", by_status)
    print(f"images described: {total_described}/{total_images}")
    for m in manifest:
        if m.status == "error":
            print(f"  ERROR {m.source_path}: {m.reason}")
    print(f"\nmanifest: {super_clean_dir / args.project / '_manifest.json'}")


if __name__ == "__main__":
    main()
