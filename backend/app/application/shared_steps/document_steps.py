"""Pipeline steps for document extraction: convert via Docling, store the raw
binary + extracted images as artifacts, then render the extracted-text
artifact. Ported and adapted from the reference architecture's
``application/shared_steps/document_steps.py`` — trimmed to the extraction
slice (no document DB, vector store, or vLLM description in this project).
"""

from __future__ import annotations

import logging

from app.application.documents import local_keys, markdown_artifact
from app.application.shared_steps.contexts import (
    HasDocument,
    HasExtractedImages,
    HasFileBytes,
    HasProjectId,
    HasTextChunks,
)
from app.domain.documents.ports import DocumentConversionClientPort, FileStoragePort
from app.pipelines.async_pipeline_step import AsyncPipelineStep

logger = logging.getLogger(__name__)


class ConvertDocumentStep(AsyncPipelineStep):
    """Convert the document binary into text chunks and extracted images via Docling.

    Calls the conversion adapter's single-pass ``convert_document`` (hybrid
    chunker + image extraction in one Docling round trip).

    Failure is non-fatal: any exception is logged and the step completes with
    empty ``context.text_chunks`` and ``context.extracted_images``.

    Requires: ``HasFileBytes``, ``HasDocument``, ``HasProjectId``, ``HasExtractedImages``, ``HasTextChunks``
    Side Effects:
        Populates ``context.text_chunks`` and ``context.extracted_images``.
    """

    REQUIRES = (
        HasFileBytes,
        HasDocument,
        HasProjectId,
        HasExtractedImages,
        HasTextChunks,
    )

    def __init__(self, conversion_client: DocumentConversionClientPort) -> None:
        super().__init__()
        self._conversion_client = conversion_client

    async def run_async(self, context: HasFileBytes) -> None:
        context.document.project_id = context.project_id
        context.document.filename = context.filename

        if not context.file_bytes:
            logger.debug("ConvertDocumentStep: no file_bytes — skipping")
            context.executed_steps.append("convert document (skipped)")
            return

        try:
            text_chunks, images = await self._conversion_client.convert_document(
                file_bytes=context.file_bytes,
                filename=context.filename or "document",
            )
            for img in images:
                img.document_id = context.document.id
            for chunk in text_chunks:
                chunk.document_id = context.document.id

            context.text_chunks = text_chunks
            context.extracted_images = images
            logger.info(
                "Converted document %s: %d text chunks, %d image(s)",
                context.document.id,
                len(text_chunks),
                len(images),
            )
        except Exception:
            logger.exception(
                "Document conversion failed for %s — continuing without chunks/images",
                context.document.id,
            )
            context.text_chunks = []
            context.extracted_images = []

        context.executed_steps.append("convert document")


class StoreFileStep(AsyncPipelineStep):
    """Persist the raw document binary as an artifact.

    Requires: ``HasFileBytes``, ``HasDocument``
    Side Effects:
        Stores the binary under ``local_keys.raw_key`` and sets
        ``context.document.file_bytes_uri``.
    """

    REQUIRES = (HasFileBytes, HasDocument)

    def __init__(self, file_storage: FileStoragePort) -> None:
        super().__init__()
        self._file_storage = file_storage
        self._stored_key: str | None = None

    async def run_async(self, context) -> None:  # context: IngestDocumentContext
        if not context.file_bytes:
            raise ValueError("StoreFileStep: no file_bytes in context")

        filename = context.filename or "document"
        key = local_keys.raw_key(context.rel_path, filename)

        uri = await self._file_storage.store(
            data=context.file_bytes,
            key=key,
            metadata={"project_id": context.project_id, "document_id": context.document.id},
        )

        self._stored_key = key
        context.document.file_bytes_uri = uri
        logger.info("Stored raw file '%s' artifact: %s", filename, uri)
        context.executed_steps.append("store file")

    async def compensate_async(self, context: HasDocument) -> None:
        if self._stored_key is not None:
            await self._file_storage.delete(key=self._stored_key)
            logger.debug("Compensated store file for key: %s", self._stored_key)
            self._stored_key = None


class StoreExtractedImagesStep(AsyncPipelineStep):
    """Persist each extracted image as an artifact.

    A single failure per image does not abort the rest — matches the
    reference architecture's per-image guarding in ``ProcessImagesStep``.

    Requires: ``HasDocument``, ``HasExtractedImages``
    Side Effects:
        For each image: writes its PNG bytes as an artifact, sets
        ``image.s3_uri``, and records the artifact's link (relative to the
        text artifact) into ``context.image_links`` keyed by position_index.
    """

    REQUIRES = (HasDocument, HasExtractedImages)

    def __init__(self, file_storage: FileStoragePort) -> None:
        super().__init__()
        self._file_storage = file_storage

    async def run_async(self, context) -> None:  # context: IngestDocumentContext
        if not context.extracted_images:
            context.executed_steps.append("store extracted images (skipped)")
            return

        stored = 0
        for image in context.extracted_images:
            if not image.data:
                logger.warning("Image %s has no data — skipping", image.id)
                continue
            try:
                key = local_keys.image_key(context.rel_path, image)
                image.s3_uri = await self._file_storage.store(
                    data=image.data,
                    key=key,
                    content_type=image.mime_type,
                    metadata={"document_id": context.document.id, "image_id": image.id},
                )
                context.image_links[image.position_index] = (
                    local_keys.image_link_from_text_artifact(context.rel_path, image)
                )
                stored += 1
            except Exception:
                logger.exception(
                    "Failed to store image %s for document %s",
                    image.id,
                    context.document.id,
                )

        logger.info(
            "StoreExtractedImagesStep: stored=%d/%d for document %s",
            stored,
            len(context.extracted_images),
            context.document.id,
        )
        context.executed_steps.append("store extracted images")


class WriteExtractedTextArtifactStep(AsyncPipelineStep):
    """Render and persist the final ``<rel_path>.md`` artifact.

    Must run after ``StoreExtractedImagesStep`` so ``context.image_links`` is
    populated before inline placeholders are substituted.

    Assembles ``document.extracted_text`` from chunks (sorted by page then
    index — see ``markdown_artifact.assemble_body_text``), inlines image
    links in document order, prepends the KB frontmatter contract, and
    appends an "Extracted images" reference table.

    Requires: ``HasDocument``, ``HasTextChunks``, ``HasExtractedImages``
    Side Effects:
        Sets ``context.document.extracted_text``, writes the rendered
        Markdown artifact, and sets ``context.document.extracted_text_uri``.
    """

    REQUIRES = (HasDocument, HasTextChunks, HasExtractedImages)

    def __init__(self, file_storage: FileStoragePort) -> None:
        super().__init__()
        self._file_storage = file_storage

    async def run_async(self, context) -> None:  # context: IngestDocumentContext
        body = markdown_artifact.assemble_body_text(context.text_chunks)
        body = markdown_artifact.inline_image_links(body, context.image_links)
        table = markdown_artifact.images_reference_table(
            context.extracted_images, context.image_links
        )
        if table:
            body = body.rstrip() + "\n\n" + table
        context.document.extracted_text = body

        page_count = markdown_artifact.page_count_from(
            context.text_chunks, context.extracted_images
        )
        rendered = (
            markdown_artifact.frontmatter(
                project=context.project_id,
                rel_path=context.rel_path,
                source_path=context.source_path,
                page_count=page_count,
                image_count=len(context.extracted_images),
            )
            + body
        )

        key = local_keys.text_key(context.rel_path)
        uri = await self._file_storage.store(
            data=rendered.encode("utf-8"),
            key=key,
            content_type="text/markdown; charset=utf-8",
            metadata={"project_id": context.project_id, "document_id": context.document.id},
        )
        context.document.extracted_text_uri = uri
        logger.debug(
            "Wrote extracted-text artifact for document %s (%d chunks, %d chars)",
            context.document.id,
            len(context.text_chunks),
            len(rendered),
        )
        context.executed_steps.append("write extracted text artifact")
