"""Extract dataset/raw/<project>/ into clean, folder-mirrored Markdown +
image artifacts via the **Docling server**, using the pipeline in
app.application.documents (see that package's docstrings for the extraction
settings — this corpus is German AEC data: railway 50 Hz schematics and
electrical plans) — see docs/DATASET_INGESTION.md for the full design and
docs/architecture/ for how this fits the backend's DDD/hexagonal layering.

    cd backend && .venv/bin/python scripts/docling_ingest.py [--project project_1]
        [--force] [--limit N] [--concurrency N] [--base-url URL] [--force-ocr]
        [--images-scale 2.0] [--describe-pictures] [-v]

The server (DOCLING_BASE_URL, default http://10.0.1.236/docling) runs the full
ML pipeline, so there is no CPU cost or per-file tiering here — every .pdf/.docx
is converted with layout + table structure + image extraction. .zip and .heic
are skipped.

--concurrency N runs up to N files against the server at once (default 1 —
sequential). Each conversion is a slow network round trip (OCR + layout +
image rendering, tens of seconds per file), so on a large corpus this matters:
185 files sequentially can take hours; --concurrency 4-8 cuts that roughly
proportionally, bounded by how much load the server can take.
--limit N caps how many *convertible* (non-skipped) files are processed -
useful for a smoke test before a full run.
--force-ocr re-OCRs every page even where a text layer exists (slower; use for
image-only scanned drawings).
--describe-pictures asks the server-side VLM to narrate each extracted picture
with an AEC-specific prompt (much slower; needs a description model on the server).
-v / --verbose prints a per-file progress line (converted/failed + timing) as
the run proceeds, instead of only the final summary.
"""
import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.documents.dataset_ingestion_service import run_project  # noqa: E402
from app.application.documents.ingest_pipeline import build_ingest_pipeline  # noqa: E402
from app.bootstrap import get_document_conversion_client, get_document_file_storage  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default="project_1")
    parser.add_argument("--force", action="store_true", help="reconvert even if output is newer")
    parser.add_argument("--limit", type=int, default=None, help="cap convertible files processed")
    parser.add_argument("--concurrency", type=int, default=1, help="max files converted in parallel (default 1)")
    parser.add_argument("--base-url", default=None, help="override DOCLING_BASE_URL")
    parser.add_argument("--force-ocr", action="store_true", help="re-OCR every page")
    parser.add_argument("--images-scale", type=float, default=None, help="page-render scale for crops")
    parser.add_argument(
        "--describe-pictures", action="store_true", help="server-side VLM picture descriptions"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="per-file progress logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    raw_dir = REPO_ROOT / "dataset" / "raw"
    clean_dir = REPO_ROOT / "dataset" / "clean"
    if not (raw_dir / args.project).exists():
        sys.exit(f"No such project: {raw_dir / args.project}")

    conversion_client = get_document_conversion_client(
        args.base_url,
        force_ocr=args.force_ocr,
        images_scale=args.images_scale,
        describe_pictures=args.describe_pictures,
    )
    file_storage = get_document_file_storage(clean_dir / args.project)
    pipeline = build_ingest_pipeline(conversion_client, file_storage)

    print(
        f"ingesting '{args.project}' (concurrency={args.concurrency}, "
        f"force={args.force}, limit={args.limit})..."
    )
    t0 = time.time()
    manifest = asyncio.run(
        run_project(
            pipeline,
            raw_dir=raw_dir,
            clean_dir=clean_dir,
            project=args.project,
            force=args.force,
            limit=args.limit,
            concurrency=args.concurrency,
        )
    )
    elapsed = time.time() - t0

    by_status: dict[str, int] = {}
    total_images = 0
    total_chunks = 0
    for m in manifest:
        by_status[m.status] = by_status.get(m.status, 0) + 1
        total_images += m.image_count
        total_chunks += m.chunk_count

    print(f"\n{len(manifest)} file(s) in {elapsed:.1f}s")
    print("by status:", by_status)
    print("images extracted:", total_images)
    print("chunks extracted:", total_chunks)
    for m in manifest:
        if m.status == "error":
            print(f"  ERROR {m.source_path}: {m.reason}")
    print(f"\nmanifest: {clean_dir / args.project / '_manifest.json'}")


if __name__ == "__main__":
    main()
