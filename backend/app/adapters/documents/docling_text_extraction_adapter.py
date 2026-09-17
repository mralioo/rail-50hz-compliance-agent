"""
DoclingTextExtractionAdapter — Adapter layer.

Lightweight document-to-text adapter backed by Docling's convert endpoint.
Use this for callers that only need plain markdown, to avoid the heavier
hybrid-chunker + image-extraction overhead.
"""
import logging

from app.adapters.documents.docling_client import DoclingClient

logger = logging.getLogger(__name__)


class DoclingTextExtractionAdapter:
    """Implements ``DocumentTextExtractionPort`` via the Docling convert endpoint."""

    def __init__(self, client: DoclingClient) -> None:
        self._client = client

    async def extract_text(self, file_bytes: bytes, filename: str) -> str:
        logger.info(
            "Extracting text from '%s' (%d bytes) via convert endpoint",
            filename,
            len(file_bytes),
        )
        return await self._client.extract_text_from_file(
            file_bytes=file_bytes,
            filename=filename,
        )
