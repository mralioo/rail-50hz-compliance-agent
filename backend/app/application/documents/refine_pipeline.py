"""Assembles the refinement pipeline and runs it for one already-extracted
document: dataset/clean/<project>/<rel_path>.md -> LLM cleanup + image
description -> dataset/super_clean/<project>/<rel_path>.md.

Mirrors ingest_pipeline.py's shape (context dataclass + build_*_pipeline +
per-file runner), one layer downstream of it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.application.documents.markdown_artifact import parse_frontmatter
from app.application.shared_steps.refinement_steps import (
    DescribeImagesStep,
    RefineTextStep,
    WriteSuperCleanArtifactStep,
)
from app.domain.documents.models import ImageDescription
from app.domain.documents.ports import FileStoragePort, ImageDescriptionPort, TextRefinementPort
from app.pipelines import BasePipelineContext, BestEffortPipelineStep, Pipeline

_IMAGE_TABLE_HEADING_RE = re.compile(r"\n##\s+Extracted images\s*\n")
_IMAGE_FILENAME_INDEX_RE = re.compile(r"^(\d+)_p")


@dataclass(kw_only=True)
class RefineDocumentContext(BasePipelineContext):
    rel_path: Path  # source-relative path, no suffix - same identity as IngestDocumentContext.rel_path
    project_id: str
    output_path: Path  # absolute: <super_clean_root>/<rel_path>.md
    frontmatter: dict  # parsed from the source dataset/clean/ artifact
    raw_body: str  # body before "## Extracted images" (or the whole body if there's none)
    image_paths: dict[int, Path] = field(default_factory=dict)  # position_index -> absolute path
    cleaned_text: str = ""
    image_descriptions: dict[int, ImageDescription] = field(default_factory=dict)


def build_refine_pipeline(
    text_refinement: TextRefinementPort,
    image_description: ImageDescriptionPort,
    file_storage: FileStoragePort,
    generative_model: str,
) -> Pipeline[RefineDocumentContext]:
    return Pipeline(
        RefineTextStep(text_refinement),
        BestEffortPipelineStep(DescribeImagesStep(image_description)),
        WriteSuperCleanArtifactStep(file_storage, generative_model),
    )


def _split_body_and_table(body: str) -> str:
    """Return the body text before the "## Extracted images" heading (or the
    whole body if there's no such section) — the old table is discarded, a
    fresh one gets rendered from the new LLM descriptions."""
    m = _IMAGE_TABLE_HEADING_RE.search(body)
    return body[: m.start()] if m else body


def _discover_images(md_path: Path) -> dict[int, Path]:
    """position_index -> absolute path, parsed from each image's filename
    (``<NNN>_p<PP>_<sha8>.png`` — see app.application.documents.local_keys),
    not from re-parsing the old markdown table."""
    images_dir = md_path.with_suffix("") / "images"
    if not images_dir.is_dir():
        return {}
    result: dict[int, Path] = {}
    for path in sorted(images_dir.glob("*.png")):
        m = _IMAGE_FILENAME_INDEX_RE.match(path.name)
        if m:
            result[int(m.group(1))] = path
    return result


async def refine_file(
    pipeline: Pipeline[RefineDocumentContext],
    *,
    project_id: str,
    clean_root: Path,
    super_clean_root: Path,
    md_path: Path,
) -> RefineDocumentContext:
    """Run the refinement pipeline for one file.

    Args:
        clean_root: the project's clean directory (``dataset/clean/<project>``).
        super_clean_root: the project's super-clean output directory
            (``dataset/super_clean/<project>``).
        md_path: absolute path to the source .md under ``clean_root``.
    """
    rel_path = md_path.relative_to(clean_root).with_suffix("")
    fields, body = parse_frontmatter(md_path.read_text())
    context = RefineDocumentContext(
        rel_path=rel_path,
        project_id=project_id,
        output_path=super_clean_root / f"{rel_path}.md",
        frontmatter=fields,
        raw_body=_split_body_and_table(body),
        image_paths=_discover_images(md_path),
    )
    await pipeline.run_async(context)
    return context
