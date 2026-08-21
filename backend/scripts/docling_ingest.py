"""Extract dataset/raw/<project>/ into clean, folder-mirrored Markdown +
images via the **Docling server** - see app.ingestion.docling_pipeline for the
extraction settings (this corpus is German AEC data: railway 50 Hz schematics
and electrical plans) and docs for how the output feeds the KB stores.

    cd backend && .venv/bin/python scripts/docling_ingest.py [--project project_1]
        [--force] [--limit N] [--base-url URL] [--force-ocr]
        [--images-scale 2.0] [--describe-pictures]

The server (DOCLING_BASE_URL, default http://10.0.1.236/docling) runs the full
ML pipeline, so there is no CPU cost or per-file tiering here - every .pdf/.docx
is converted with layout + table structure + image extraction. .zip and .heic
are skipped.

--limit N caps how many convertible (non-skipped) files are processed - useful
for a smoke test before a full run.
--force-ocr re-OCRs every page even where a text layer exists (slower; use for
image-only scanned drawings).
--describe-pictures asks the server-side VLM to narrate each extracted picture
with an AEC-specific prompt (much slower; needs a description model on the server).
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.docling_pipeline import run_sync  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default="project_1")
    parser.add_argument("--force", action="store_true", help="reconvert even if output is newer")
    parser.add_argument("--limit", type=int, default=None, help="cap convertible files processed")
    parser.add_argument("--base-url", default=None, help="override DOCLING_BASE_URL")
    parser.add_argument("--force-ocr", action="store_true", help="re-OCR every page")
    parser.add_argument("--images-scale", type=float, default=2.0, help="page-render scale for crops")
    parser.add_argument(
        "--describe-pictures", action="store_true", help="server-side VLM picture descriptions"
    )
    args = parser.parse_args()

    raw_dir = REPO_ROOT / "dataset" / "raw"
    clean_dir = REPO_ROOT / "dataset" / "clean"
    if not (raw_dir / args.project).exists():
        sys.exit(f"No such project: {raw_dir / args.project}")

    t0 = time.time()
    manifest = run_sync(
        raw_dir,
        clean_dir,
        args.project,
        force=args.force,
        limit=args.limit,
        base_url=args.base_url,
        force_ocr=args.force_ocr,
        images_scale=args.images_scale,
        describe_pictures=args.describe_pictures,
    )
    elapsed = time.time() - t0

    by_status: dict[str, int] = {}
    total_images = 0
    for m in manifest:
        by_status[m.status] = by_status.get(m.status, 0) + 1
        total_images += m.image_count

    print(f"{len(manifest)} file(s) in {elapsed:.1f}s")
    print("by status:", by_status)
    print("images extracted:", total_images)
    for m in manifest:
        if m.status == "error":
            print(f"  ERROR {m.source_path}: {m.reason}")
    print(f"\nmanifest: {clean_dir / args.project / '_manifest.json'}")


if __name__ == "__main__":
    main()
