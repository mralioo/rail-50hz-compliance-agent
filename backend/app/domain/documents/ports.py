"""The `documents` bounded context's ports: what the domain needs from
document conversion and artifact storage, not how any particular technology
does it — see `app/domain/cad/ports.py` for the pattern this follows, and
`app/adapters/documents/` for the concrete Docling/local-filesystem
implementations, wired in `app/bootstrap.py`.
"""
from abc import ABC, abstractmethod
from typing import Optional, Protocol

from app.domain.documents.models import Chunk, ExtractedImage, ImageDescription


class DocumentConversionClientPort(Protocol):
    """Single-pass document conversion: text chunks + extracted images in one call.

    Implementations call an external service (e.g. Docling) once and return both
    the semantically-chunked text and any images embedded in the document.
    This avoids the double-conversion penalty of calling separate chunking and
    image-extraction endpoints.
    """

    async def convert_document(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> tuple[list[Chunk], list[ExtractedImage]]:
        """
        Convert a document file, returning text chunks and extracted images.

        Args:
            file_bytes: Raw document bytes (PDF, DOCX, PPTX, etc.)
            filename: Original filename — used to determine file type.

        Returns:
            Tuple of:
              - list[Chunk]: ordered semantic text chunks (document_id set to "" — filled by ConvertDocumentStep)
              - list[ExtractedImage]: images with data, mime_type, checksum, page_number populated
        """
        ...


class DocumentTextExtractionPort(ABC):
    """Port for lightweight document-to-text conversion.

    Callers that only need plain markdown text from a document should depend
    on this port rather than ``DocumentConversionClientPort``, which also
    triggers the heavier hybrid-chunker + image extraction.
    """

    @abstractmethod
    async def extract_text(self, file_bytes: bytes, filename: str) -> str:
        """Convert a document to a plain markdown string.

        Returns:
            Extracted markdown text (may be empty if the document yields nothing).
        """


class TextRefinementPort(ABC):
    """Port for LLM-based cleanup of already-extracted document text.

    Docling's OCR/layout output can carry extraction artifacts — repeated
    characters/lines, broken line-wraps, stray whitespace — that a similarity
    search embeds right along with the real content. Implementations must
    preserve every real technical detail (part numbers, measurements, German
    terms, table data) and must not summarize, translate, or add commentary —
    this is cleanup, not rewriting.
    """

    @abstractmethod
    async def refine_text(self, raw_text: str) -> str:
        """Return a cleaned version of ``raw_text``. May return it unchanged
        if nothing needed fixing."""


class ImageDescriptionPort(ABC):
    """Port for describing an extracted image via a vision-capable LLM.

    Produces a short natural-language description plus a category from a
    fixed, corpus-grounded taxonomy (see the adapter for the actual list) —
    both far richer signal for clustering/retrieval than Docling's own
    coarse picture-classification label alone.
    """

    @abstractmethod
    async def describe_image(self, image_bytes: bytes) -> ImageDescription:
        """Describe and categorize a single image."""


class FileStoragePort(ABC):
    """
    Port for storing and retrieving files as binary objects — the "artifact
    store" for extracted text and images.

    Implementations may target S3-compatible backends (AWS S3, MinIO, Garage),
    local filesystem (see adapters/documents/local_file_storage_adapter.py,
    used by this project), or no-op fakes for testing.

    Files are addressed by a string key (e.g.
    ``projects/{project_id}/documents/{document_id}/raw/{filename}``, see
    ``storage_keys.py``). The ``store`` method returns a full URI that can be
    persisted on the Document model for later retrieval.
    """

    @abstractmethod
    async def store(
        self,
        *,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """Store binary data at *key* and return a URI to the stored object."""
        ...

    @abstractmethod
    async def retrieve(self, *, key: str) -> Optional[bytes]:
        """Retrieve binary data by *key*. Returns ``None`` if the key doesn't exist."""
        ...

    @abstractmethod
    async def delete(self, *, key: str) -> None:
        """Delete the object at *key*. No-op if the key does not exist."""
        ...

    @abstractmethod
    async def exists(self, *, key: str) -> bool:
        """Return ``True`` if an object exists at *key*."""
        ...

    @abstractmethod
    async def list_keys(self, *, prefix: str) -> list[str]:
        """Return all keys that start with *prefix*."""
        ...
