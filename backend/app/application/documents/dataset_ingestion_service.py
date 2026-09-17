"""Batch use-case: walk ``dataset/raw/<project>/``, run the ingest pipeline
over every convertible file, and write a manifest — the top-level orchestration
``scripts/docling_ingest.py`` drives.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from app.application.documents.ingest_pipeline import Pipeline, ingest_file
from app.pipelines import PipelineError

logger = logging.getLogger(__name__)

_CONVERTIBLE_SUFFIXES = {".pdf", ".docx"}
_SKIP_REASONS = {
    ".zip": "redundant archive",
    ".heic": "image, no extractable text",
}


class Status(Enum):
    OK = "ok"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class ManifestEntry:
    source_path: str
    output_path: str | None
    status: str
    image_count: int = 0
    chunk_count: int = 0
    reason: str | None = None


def classify(path: Path) -> tuple[bool, str | None]:
    """(convertible, skip_reason)."""
    suffix = path.suffix.lower()
    if suffix in _SKIP_REASONS:
        return False, _SKIP_REASONS[suffix]
    if suffix in _CONVERTIBLE_SUFFIXES:
        return True, None
    return False, f"unsupported file type: {suffix}"


async def _convert_one(
    pipeline: Pipeline,
    *,
    project: str,
    raw_root: Path,
    path: Path,
    rel_with_suffix: Path,
    out_path: Path,
    semaphore: asyncio.Semaphore,
) -> ManifestEntry:
    async with semaphore:
        t0 = time.monotonic()
        try:
            context = await ingest_file(
                pipeline, project_id=project, raw_root=raw_root, path=path
            )
            logger.info(
                "converted %s (%d chunks, %d images) in %.1fs",
                rel_with_suffix,
                len(context.text_chunks),
                len(context.extracted_images),
                time.monotonic() - t0,
            )
            return ManifestEntry(
                str(rel_with_suffix),
                str(out_path),
                Status.OK.value,
                image_count=len(context.extracted_images),
                chunk_count=len(context.text_chunks),
            )
        except PipelineError as exc:
            logger.warning(
                "FAILED %s after %.1fs: %s: %s",
                rel_with_suffix,
                time.monotonic() - t0,
                exc.failed_step,
                exc.cause,
            )
            return ManifestEntry(
                str(rel_with_suffix),
                None,
                Status.ERROR.value,
                reason=f"{exc.failed_step}: {exc.cause}",
            )


async def run_project(
    pipeline: Pipeline,
    *,
    raw_dir: Path,
    clean_dir: Path,
    project: str,
    force: bool = False,
    limit: int | None = None,
    concurrency: int = 1,
) -> list[ManifestEntry]:
    """Walk the project's raw corpus and convert every eligible file.

    ``concurrency`` bounds how many files are in flight against the Docling
    server at once (each ``ingest_file`` call is a slow network round trip —
    OCR + layout + image rendering — so running them sequentially on a large
    corpus can take hours; a handful in parallel cuts that substantially
    without overloading a shared server).

    Classification, cache, and ``--limit`` bookkeeping run first as a cheap
    sequential pass (no network calls); only files that actually need
    conversion go through the bounded-concurrency pass.
    """
    raw_root = raw_dir / project
    clean_root = clean_dir / project
    manifest: list[ManifestEntry | None] = []
    pending: list[tuple[int, Path, Path, Path]] = []  # (manifest_index, path, rel, out_path)
    n_processed = 0

    for path in sorted(raw_root.rglob("*")):
        if not path.is_file():
            continue
        rel_with_suffix = path.relative_to(raw_root)
        out_path = clean_root / rel_with_suffix.with_suffix(".md")

        convertible, skip_reason = classify(path)
        if not convertible:
            manifest.append(
                ManifestEntry(str(rel_with_suffix), None, Status.SKIPPED.value, reason=skip_reason)
            )
            continue

        if limit is not None and n_processed >= limit:
            manifest.append(
                ManifestEntry(
                    str(rel_with_suffix), None, Status.SKIPPED.value, reason="over --limit"
                )
            )
            continue

        if out_path.exists() and not force and out_path.stat().st_mtime >= path.stat().st_mtime:
            manifest.append(
                ManifestEntry(str(rel_with_suffix), str(out_path), Status.OK.value, reason="cached")
            )
            n_processed += 1
            continue

        manifest.append(None)  # placeholder, filled in by the concurrent pass below
        pending.append((len(manifest) - 1, path, rel_with_suffix, out_path))
        n_processed += 1

    if pending:
        semaphore = asyncio.Semaphore(max(1, concurrency))
        results = await asyncio.gather(
            *[
                _convert_one(
                    pipeline,
                    project=project,
                    raw_root=raw_root,
                    path=path,
                    rel_with_suffix=rel,
                    out_path=out_path,
                    semaphore=semaphore,
                )
                for _, path, rel, out_path in pending
            ]
        )
        for (idx, *_), entry in zip(pending, results):
            manifest[idx] = entry

    clean_root.mkdir(parents=True, exist_ok=True)
    (clean_root / "_manifest.json").write_text(
        json.dumps([asdict(m) for m in manifest], indent=2, ensure_ascii=False)
    )
    return manifest
