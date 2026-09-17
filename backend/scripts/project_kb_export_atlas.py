"""Export the local project-document vector index (`rail50hz_project_docs`,
see app.kb.project_opensearch_store) to Parquet for visualization with
Apple's Embedding Atlas (https://github.com/apple/embedding-atlas).

Exports the *actual* stored embeddings (computed via OPENSEARCH_EMBEDDING_PROVIDER,
e.g. the remote vLLM e5-large model — see docs/OPENSEARCH_NEO4J_EVALUATION.md
§9.3) rather than letting Embedding Atlas re-embed the text itself, so what
you see is the real vector space that's actually stored and queried.

Writes TWO tables (see docs/OPENSEARCH_NEO4J_EVALUATION.md §9.6):
- `<project>.parquet` — one row per chunk (text + vector + the chunk's own
  first image, if any) — the main scatter/projection table.
- `<project>_images.parquet` — one row per *unique* image (deduplicated by
  path) at full resolution, with its category/description and a back-
  reference to the owning chunk — a dedicated table Embedding Atlas loads as
  its own panel via `--table images ...`, so images are browsable on their
  own instead of only as a small tooltip thumbnail on their owning chunk.

Both tables store the image as an explicit `data:image/png;base64,...` URI
(not a bare base64 string) — this is one of Embedding Atlas's documented
image formats and removes any ambiguity for the renderer.

Storage strategy: each chunk's own images (path/category/description) were
already resolved to real filesystem paths and stored *on the chunk's
OpenSearch document* at ingest time (app.kb.project_corpus._extract_images) -
this script does a pure read of that, never re-deriving anything from the
filesystem layout itself.

Requires the local KB evaluation stack running (`make kb-up`) and documents
already indexed (`make kb-ingest-project` / `make reindex-refined`).

    .venv/bin/python scripts/project_kb_export_atlas.py [--project project_1]
        [--out-dir workdir/atlas]

Then visualize with (or just `make visualize-embeddings PROJECT=project_1`):

    .venv/bin/embedding-atlas workdir/atlas/project_1.parquet \\
        --text text --vector embedding --image image \\
        --table images workdir/atlas/project_1_images.parquet \\
        --table-relation images 'mainKey=chunk_id;key=chunk_id'
"""
import argparse
import base64
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402
from opensearchpy import OpenSearch, helpers  # noqa: E402
from PIL import Image  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.kb.project_opensearch_store import PROJECT_INDEX  # noqa: E402

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT_DIR = REPO_ROOT / "backend" / "workdir" / "atlas"


def _data_url(path_str: str) -> tuple[str | None, int | None, int | None]:
    """(data:image/png;base64 URI, width, height) for a real image file, or
    (None, None, None) if it's missing/unreadable - degrades gracefully, one
    bad image must not break the export."""
    path = Path(path_str)
    try:
        data = path.read_bytes()
        with Image.open(path) as im:
            width, height = im.size
        return f"data:image/png;base64,{base64.b64encode(data).decode('ascii')}", width, height
    except (OSError, ValueError):
        logger.warning("image file missing or unreadable, skipping: %s", path)
        return None, None, None


def _fetch_chunks(project: str) -> list[dict]:
    settings = get_settings()
    client = OpenSearch(hosts=[settings.opensearch_host])
    query = {"query": {"term": {"project": project}}} if project else {"query": {"match_all": {}}}
    return [
        {"chunk_id": hit["_id"], **hit["_source"]}
        for hit in helpers.scan(client, index=PROJECT_INDEX, query=query, preserve_order=False)
    ]


def export_chunks(chunks: list[dict], out_path: Path) -> int:
    """Main table: one row per chunk, its vector, and (if any) its own first image."""
    rows = []
    for src in chunks:
        images = src.get("images") or []
        first = images[0] if images else {}
        data_url, width, height = _data_url(first["path"]) if first else (None, None, None)
        rows.append(
            {
                "chunk_id": src["chunk_id"],
                "project": src.get("project", ""),
                "substation": src.get("substation", ""),
                "category": src.get("category", ""),
                "source_path": src.get("source_path", ""),
                "doc_name": src.get("doc_name", ""),
                "heading": src.get("heading", ""),
                "text": src.get("text", ""),
                "embedding": src.get("embedding"),
                "image": data_url,
                "image_category": first.get("category", ""),
                "image_description": first.get("description", ""),
                "image_count": len(images),
            }
        )
    if not rows:
        return 0
    df = pd.DataFrame(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return len(df)


def export_images(chunks: list[dict], out_path: Path) -> int:
    """Dedicated image table: one row per unique image (deduped by path),
    at full resolution, with a back-reference (chunk_id) to its owning chunk
    for cross-filtering with the main table via --table-relation."""
    seen: dict[str, dict] = {}
    for src in chunks:
        for img in src.get("images") or []:
            path = img.get("path", "")
            if not path or path in seen:
                continue
            seen[path] = {
                "chunk_id": src["chunk_id"],
                "project": src.get("project", ""),
                "substation": src.get("substation", ""),
                "category": src.get("category", ""),
                "doc_name": src.get("doc_name", ""),
                "source_path": src.get("source_path", ""),
                "file": img.get("file", ""),
                "path": path,
                "image_category": img.get("category", ""),
                "description": img.get("description", ""),
            }

    rows = []
    for entry in seen.values():
        data_url, width, height = _data_url(entry["path"])
        if data_url is None:
            continue
        rows.append({**entry, "image": data_url, "width": width, "height": height})

    if not rows:
        return 0
    df = pd.DataFrame(rows).drop(columns=["path"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(out_path, index=False)
    return len(df)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", default="project_1", help="project id to filter by (empty string = all projects)")
    parser.add_argument("--out-dir", default=None, help="output directory for both parquet files")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.opensearch_enabled:
        sys.exit("Set OPENSEARCH_ENABLED=true in backend/.env first.")

    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT_DIR
    project_label = args.project or "all"
    chunks_path = out_dir / f"{project_label}.parquet"
    images_path = out_dir / f"{project_label}_images.parquet"

    chunks = _fetch_chunks(args.project)
    if not chunks:
        sys.exit(
            f"No chunks found for project {args.project!r} in index {PROJECT_INDEX!r} — "
            "run `make kb-ingest-project` first."
        )

    chunk_count = export_chunks(chunks, chunks_path)
    image_count = export_images(chunks, images_path)

    with_thumb = int(pd.read_parquet(chunks_path, columns=["image"])["image"].notna().sum())
    print(f"Exported {chunk_count} chunk(s) to {chunks_path} ({with_thumb} with a thumbnail image)")
    print(f"Exported {image_count} unique image(s) to {images_path}")
    print(
        "\nVisualize with:\n"
        f"  .venv/bin/embedding-atlas {chunks_path} \\\n"
        "      --text text --vector embedding --image image \\\n"
        f"      --table images {images_path} \\\n"
        "      --table-relation images 'mainKey=chunk_id;key=chunk_id'"
    )


if __name__ == "__main__":
    main()
