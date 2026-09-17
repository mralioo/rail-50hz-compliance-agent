"""Assembles the document-extraction pipeline and runs it for one file.

Mirrors the reference architecture's ``application/document_management/
pipelines`` (pipeline assembly) — trimmed to the extraction slice: Convert →
StoreFile → StoreExtractedImages (best-effort) → WriteExtractedTextArtifact.
No DocumentRepository/vector-store/description steps in this project.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.application.shared_steps.contexts import (
    HasDocument,
    HasExtractedImages,
    HasFileBytes,
    HasProjectId,
    HasTextChunks,
)
from app.application.shared_steps.document_steps import (
    ConvertDocumentStep,
    StoreExtractedImagesStep,
    StoreFileStep,
    WriteExtractedTextArtifactStep,
)
from app.domain.documents.models import Document
from app.domain.documents.ports import DocumentConversionClientPort, FileStoragePort
from app.pipelines import BasePipelineContext, BestEffortPipelineStep, Pipeline


@dataclass(kw_only=True)
class IngestDocumentContext(
    BasePipelineContext,
    HasFileBytes,
    HasDocument,
    HasProjectId,
    HasExtractedImages,
    HasTextChunks,
):
    """Extends the shared mixins with the fields specific to local-artifact
    ingestion (source-path-mirrored keys instead of a document DB)."""

    rel_path: Path  # source-relative path, no suffix — the artifact "document id"
    source_path: Path  # source-relative path, with suffix — for frontmatter
    image_links: dict[int, str] = field(default_factory=dict)


def build_ingest_pipeline(
    conversion_client: DocumentConversionClientPort,
    file_storage: FileStoragePort,
) -> Pipeline[IngestDocumentContext]:
    return Pipeline(
        ConvertDocumentStep(conversion_client),
        StoreFileStep(file_storage),
        BestEffortPipelineStep(StoreExtractedImagesStep(file_storage)),
        WriteExtractedTextArtifactStep(file_storage),
    )


def make_document_id(project_id: str, rel_path: Path) -> str:
    """Deterministic id derived from the source path (not a random UUID):
    there is no document database to persist an id mapping in, so reruns must
    resolve to the same artifact locations without keeping external state."""
    return f"{project_id}:{rel_path.as_posix()}"


async def ingest_file(
    pipeline: Pipeline[IngestDocumentContext],
    *,
    project_id: str,
    raw_root: Path,
    path: Path,
) -> IngestDocumentContext:
    """Run the pipeline for a single source file.

    Args:
        raw_root: the project's raw directory (``dataset/raw/<project>``).
        path: absolute path to the source file under ``raw_root``.
    """
    rel_with_suffix = path.relative_to(raw_root)
    rel_path = rel_with_suffix.with_suffix("")
    document = Document(
        id=make_document_id(project_id, rel_path),
        project_id=project_id,
        filename=path.name,
    )
    context = IngestDocumentContext(
        file_bytes=path.read_bytes(),
        filename=path.name,
        document=document,
        project_id=project_id,
        rel_path=rel_path,
        source_path=rel_with_suffix,
    )
    await pipeline.run_async(context)
    return context
