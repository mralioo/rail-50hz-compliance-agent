"""Pipeline steps for the refinement layer: LLM-based cleanup of already-
extracted text, and LLM-based description/categorization of already-
extracted images — reads dataset/clean/<project>/, writes
dataset/super_clean/<project>/. See docs/DOCUMENT_EXTRACTION.md.
"""
from __future__ import annotations

import logging
from pathlib import Path

from app.application.documents import markdown_artifact, refine_markdown
from app.domain.documents.ports import (
    FileStoragePort,
    ImageDescriptionPort,
    TextRefinementPort,
)
from app.pipelines.async_pipeline_step import AsyncPipelineStep

logger = logging.getLogger(__name__)


class RefineTextStep(AsyncPipelineStep):
    """Clean OCR/extraction noise out of the document body via an LLM.

    Converts existing ``![picture N](...)`` links to ``<!-- image N -->``
    markers first (an LLM asked to "clean" text must not be trusted to leave
    markdown link syntax untouched), and instructs the model to preserve
    them — ``WriteSuperCleanArtifactStep`` resolves them back to real
    descriptions afterward.

    Side Effects:
        Sets ``context.cleaned_text``.
    """

    def __init__(self, text_refinement: TextRefinementPort) -> None:
        super().__init__()
        self._text_refinement = text_refinement

    async def run_async(self, context) -> None:  # context: RefineDocumentContext
        marked = refine_markdown.markers_from_links(context.raw_body)
        try:
            context.cleaned_text = await self._text_refinement.refine_text(marked)
        except Exception:
            logger.exception(
                "RefineTextStep: cleanup failed for %s — keeping original text",
                context.rel_path,
            )
            context.cleaned_text = marked
        context.executed_steps.append("refine text")


class DescribeImagesStep(AsyncPipelineStep):
    """Describe and categorize each of the document's already-extracted images.

    Per-image failures are caught individually so one bad image doesn't lose
    descriptions for the rest of the document.

    Side Effects:
        Populates ``context.image_descriptions`` (keyed by the position index
        parsed from each image's filename).
    """

    def __init__(self, image_description: ImageDescriptionPort) -> None:
        super().__init__()
        self._image_description = image_description

    async def run_async(self, context) -> None:  # context: RefineDocumentContext
        if not context.image_paths:
            context.executed_steps.append("describe images (skipped)")
            return

        described = 0
        for idx, path in context.image_paths.items():
            try:
                data = path.read_bytes()
                context.image_descriptions[idx] = await self._image_description.describe_image(data)
                described += 1
            except Exception:
                logger.exception(
                    "DescribeImagesStep: failed for %s image[%d] (%s)",
                    context.rel_path,
                    idx,
                    path.name,
                )

        logger.info(
            "DescribeImagesStep: described=%d/%d for %s",
            described,
            len(context.image_paths),
            context.rel_path,
        )
        context.executed_steps.append("describe images")


class WriteSuperCleanArtifactStep(AsyncPipelineStep):
    """Render and persist the final super-clean ``.md`` artifact.

    Side Effects:
        Writes the rendered Markdown to ``dataset/super_clean/<project>/
        <rel_path>.md`` via the file storage port.
    """

    def __init__(self, file_storage: FileStoragePort, generative_model: str) -> None:
        super().__init__()
        self._file_storage = file_storage
        self._generative_model = generative_model

    async def run_async(self, context) -> None:  # context: RefineDocumentContext
        links = {
            idx: refine_markdown.relative_image_link(
                context.output_path, path
            )
            for idx, path in context.image_paths.items()
        }
        body = refine_markdown.inline_descriptions(
            context.cleaned_text, context.image_descriptions, links
        )
        table = refine_markdown.images_reference_table(
            [context.image_paths[i] for i in sorted(context.image_paths)],
            context.image_descriptions,
            links,
        )
        if table:
            body = body.rstrip() + "\n\n" + table

        page_count_raw = context.frontmatter.get("page_count")
        page_count = int(page_count_raw) if page_count_raw not in (None, "null") else None
        fm = markdown_artifact.frontmatter(
            project=context.project_id,
            rel_path=context.rel_path,
            source_path=Path(context.frontmatter.get("source_path", "")),
            page_count=page_count,
            image_count=len(context.image_paths),
            extra={"refinement_model": self._generative_model},
        )
        rendered = fm + body

        key = f"{context.rel_path.as_posix()}.md"
        await self._file_storage.store(
            data=rendered.encode("utf-8"),
            key=key,
            content_type="text/markdown; charset=utf-8",
            metadata={"project_id": context.project_id},
        )
        context.executed_steps.append("write super-clean artifact")
