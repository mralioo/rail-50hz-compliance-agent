"""Context mixin base classes for pipeline steps.

Ported (trimmed to what the document-extraction slice needs) from the
reference architecture's ``application/shared_steps/contexts.py``. Each mixin
is a dataclass that declares a specific group of fields; pipeline steps
type-hint their ``run_async`` method against the mixin(s) they require,
making dependencies explicit.
"""
from dataclasses import dataclass, field
from typing import Optional

from app.domain.documents.models import Chunk, Document, ExtractedImage


@dataclass(kw_only=True)
class HasFileBytes:
    file_bytes: Optional[bytes] = None
    filename: Optional[str] = None


@dataclass(kw_only=True)
class HasDocument:
    document: Document


@dataclass(kw_only=True)
class HasProjectId:
    project_id: str | None = None


@dataclass(kw_only=True)
class HasExtractedImages:
    """Images extracted from the document (populated by ConvertDocumentStep)."""

    extracted_images: list[ExtractedImage] = field(default_factory=list)


@dataclass(kw_only=True)
class HasTextChunks:
    """Semantic text chunks (populated by ConvertDocumentStep)."""

    text_chunks: list[Chunk] = field(default_factory=list)
