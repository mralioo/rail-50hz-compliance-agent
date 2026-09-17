"""Smoke test: run the real Docling-server extraction pipeline on one sample
PDF and print a quality report — chunk/text stats, every extracted image
(page, size, classification, caption), and the rendered Markdown artifact —
so you can eyeball whether the AEC tuning (German OCR, picture classification,
2x page-render scale) is actually working on this corpus's schematics and
electrical plans.

Does not touch dataset/clean/ — writes into a scratch directory
(backend/workdir/smoke_test/<file-stem>/) so it never collides with a real
ingestion run.

    cd backend && .venv/bin/python scripts/smoke_test_extraction.py
        [--file PATH] [--base-url URL] [--force-ocr] [--describe-pictures]
        [--print-markdown]

With no --file, defaults to a real schematic from dataset/raw/project_1
(a single-line diagram — Übersichtsschema — representative of this corpus's
image-heavy, text-sparse plan PDFs).

Known environment caveat (this dev box only): a path-MTU blackhole between
this WSL2 host and the Docling server truncates large multipart uploads
(WriteTimeout / ReadError / RemoteProtocolError around ~39KB sent). If you hit
that, run `sudo ip link set dev eth0 mtu 1380` first, or run this script from
a host without that network fault.
"""
import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.adapters.documents.local_file_storage_adapter import LocalFileStorageAdapter  # noqa: E402
from app.application.documents.ingest_pipeline import build_ingest_pipeline, ingest_file  # noqa: E402
from app.bootstrap import get_docling_client, get_document_conversion_client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE = (
    REPO_ROOT
    / "dataset"
    / "raw"
    / "project_1"
    / "20250413_Abgabe50Hz_Strecke5919"
    / "ESTW_A Ilmenau"
    / "Übersichtsschema"
    / "1633028233_Info.pdf"
)

_NETWORK_HINT = (
    "\nThis looks like the known dev-box path-MTU blackhole (large multipart\n"
    "uploads to the Docling server stall/drop mid-transfer). Try:\n"
    "  sudo ip link set dev eth0 mtu 1380\n"
    "then re-run this script. If you're not on that box, check DOCLING_BASE_URL\n"
    "and that the server is reachable."
)


async def main_async(args: argparse.Namespace) -> None:
    sample = Path(args.file) if args.file else DEFAULT_SAMPLE
    if not sample.exists():
        sys.exit(f"Sample file not found: {sample}")

    client = get_docling_client(args.base_url)
    print(f"Docling server: {client.base_url}")
    healthy = await client.health_check()
    print(f"health check: {'OK' if healthy else 'UNREACHABLE'}")
    if not healthy:
        sys.exit(1)

    conversion_client = get_document_conversion_client(
        args.base_url,
        force_ocr=args.force_ocr,
        describe_pictures=args.describe_pictures,
    )
    out_root = REPO_ROOT / "backend" / "workdir" / "smoke_test"
    file_storage = LocalFileStorageAdapter(root=out_root)
    pipeline = build_ingest_pipeline(conversion_client, file_storage)

    size = sample.stat().st_size
    print(f"\nsample: {sample}")
    print(f"size: {size:,} bytes")
    print("converting (this hits the live Docling server — may take a while for OCR + rendering)...")

    t0 = time.time()
    try:
        context = await ingest_file(
            pipeline,
            project_id="smoke_test",
            raw_root=sample.parent,
            path=sample,
        )
    except Exception as exc:
        elapsed = time.time() - t0
        print(f"\nFAILED after {elapsed:.1f}s: {type(exc).__name__}: {exc}")
        if type(exc).__name__ in ("WriteTimeout", "ReadError", "RemoteProtocolError", "ReadTimeout"):
            print(_NETWORK_HINT)
        raise
    elapsed = time.time() - t0

    text_len = len(context.document.extracted_text)
    print(f"\ndone in {elapsed:.1f}s")
    print("=" * 60)
    print("QUALITY REPORT")
    print("=" * 60)
    print(f"chunks:          {len(context.text_chunks)}")
    print(f"extracted chars: {text_len}")
    print(f"images found:    {len(context.extracted_images)}")
    print(f"raw artifact:    {context.document.file_bytes_uri}")
    print(f"text artifact:   {context.document.extracted_text_uri}")

    if context.extracted_images:
        print("\nimages:")
        for img in context.extracted_images:
            cap = (img.caption or "").strip().replace("\n", " ")
            print(
                f"  [{img.position_index}] page={img.page_number} "
                f"{img.width}x{img.height} {img.size_bytes}B "
                f"class={img.classification!r} caption={cap[:80]!r}"
            )
    else:
        print("\nNo images extracted — for a schematic-heavy PDF this usually means either")
        print("the page has no embedded pictures Docling detected, or every crop was")
        print("filtered as too small. Check --describe-pictures / server logs if unexpected.")

    if text_len == 0:
        print("\nWARNING: zero extracted text — OCR may not be firing, or the page is pure vector art")
        print("with no recognizable text/labels.")

    if args.print_markdown:
        text_key_path = LocalFileStorageAdapter.path_from_uri(context.document.extracted_text_uri)
        print("\n" + "=" * 60)
        print(f"RENDERED MARKDOWN ({text_key_path})")
        print("=" * 60)
        print(text_key_path.read_text())

    print(f"\nartifacts written under: {out_root}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", default=None, help="path to a real sample PDF/DOCX (default: a schematic from dataset/raw/project_1)")
    parser.add_argument("--base-url", default=None, help="override DOCLING_BASE_URL")
    parser.add_argument("--force-ocr", action="store_true", help="re-OCR every page even where a text layer exists")
    parser.add_argument("--describe-pictures", action="store_true", help="also ask the server-side VLM to describe each picture (slower)")
    parser.add_argument("--print-markdown", action="store_true", help="print the full rendered Markdown artifact")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
