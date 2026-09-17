"""Batch use-case: walk dataset/clean/<project>/, run the refinement pipeline
over every extracted document, and write a manifest — the top-level
orchestration scripts/docling_refine.py drives. Mirrors
dataset_ingestion_service.py, one layer downstream of it.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from app.application.documents.refine_pipeline import Pipeline, refine_file
from app.pipelines import PipelineError

logger = logging.getLogger(__name__)


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
    described_count: int = 0
    reason: str | None = None


async def _refine_one(
    pipeline: Pipeline,
    *,
    project: str,
    clean_root: Path,
    super_clean_root: Path,
    md_path: Path,
    rel_with_suffix: Path,
    semaphore: asyncio.Semaphore,
) -> ManifestEntry:
    async with semaphore:
        t0 = time.monotonic()
        try:
            context = await refine_file(
                pipeline,
                project_id=project,
                clean_root=clean_root,
                super_clean_root=super_clean_root,
                md_path=md_path,
            )
            logger.info(
                "refined %s (%d/%d images described) in %.1fs",
                rel_with_suffix,
                len(context.image_descriptions),
                len(context.image_paths),
                time.monotonic() - t0,
            )
            return ManifestEntry(
                str(rel_with_suffix),
                str(context.output_path),
                Status.OK.value,
                image_count=len(context.image_paths),
                described_count=len(context.image_descriptions),
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
                str(rel_with_suffix), None, Status.ERROR.value, reason=f"{exc.failed_step}: {exc.cause}"
            )


async def run_project(
    pipeline: Pipeline,
    *,
    clean_dir: Path,
    super_clean_dir: Path,
    project: str,
    force: bool = False,
    limit: int | None = None,
    concurrency: int = 1,
) -> list[ManifestEntry]:
    clean_root = clean_dir / project
    super_clean_root = super_clean_dir / project
    manifest: list[ManifestEntry | None] = []
    pending: list[tuple[int, Path, Path]] = []  # (manifest_index, md_path, rel_with_suffix)
    n_processed = 0

    for md_path in sorted(clean_root.rglob("*.md")):
        rel_with_suffix = md_path.relative_to(clean_root)
        out_path = super_clean_root / rel_with_suffix

        if limit is not None and n_processed >= limit:
            manifest.append(
                ManifestEntry(str(rel_with_suffix), None, Status.SKIPPED.value, reason="over --limit")
            )
            continue

        if out_path.exists() and not force and out_path.stat().st_mtime >= md_path.stat().st_mtime:
            manifest.append(
                ManifestEntry(str(rel_with_suffix), str(out_path), Status.OK.value, reason="cached")
            )
            n_processed += 1
            continue

        manifest.append(None)
        pending.append((len(manifest) - 1, md_path, rel_with_suffix))
        n_processed += 1

    if pending:
        semaphore = asyncio.Semaphore(max(1, concurrency))
        results = await asyncio.gather(
            *[
                _refine_one(
                    pipeline,
                    project=project,
                    clean_root=clean_root,
                    super_clean_root=super_clean_root,
                    md_path=md_path,
                    rel_with_suffix=rel_with_suffix,
                    semaphore=semaphore,
                )
                for _, md_path, rel_with_suffix in pending
            ]
        )
        for (idx, *_), entry in zip(pending, results):
            manifest[idx] = entry

    super_clean_root.mkdir(parents=True, exist_ok=True)
    (super_clean_root / "_manifest.json").write_text(
        json.dumps([asdict(m) for m in manifest], indent=2, ensure_ascii=False)
    )
    return manifest
