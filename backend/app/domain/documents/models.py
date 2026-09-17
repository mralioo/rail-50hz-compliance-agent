"""The `documents` bounded context's domain models: the entities the
extraction pipeline produces, independent of how they're converted or stored.

Ported from the reference architecture (ITUKI's `domain/data/documents/
models/`), consolidated into one file to match this repo's per-context
convention (see `app/domain/cad/ports.py` — one file per concern, not one
file per class).
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Document:
    """
    Core document entity representing a processed document.

    Uses URI references to stored binary data rather than holding bytes
    directly. This enables efficient storage and retrieval through
    configurable storage backends (local filesystem for now — see
    adapters/documents/local_file_storage_adapter.py; swap for S3/Garage
    without touching this model).
    """

    id: str
    project_id: str = "default_project"
    filename: Optional[str] = None

    # URI references to stored data (populated after storage steps)
    file_bytes_uri: Optional[str] = None  # URI to raw binary in storage
    extracted_text_uri: Optional[str] = None  # URI to extracted text in storage
    extracted_images_uri: Optional[str] = None  # URI pattern for extracted images

    # Transient data (not persisted, used during pipeline processing)
    file_bytes: Optional[bytes] = field(default=None, repr=False)
    extracted_text: str = ""

    metadata: dict = field(default_factory=dict)


@dataclass
class Chunk:
    id: str
    document_id: str
    text: str
    index: int
    embedding: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class ExtractedImage:
    """
    Image extracted from a document during processing.
    Contains both the image data and positional/contextual metadata.
    """

    id: str  # UUID - used in markdown placeholders
    document_id: str  # FK to Document
    data: bytes  # Image binary data
    mime_type: str  # image/png, image/jpeg, etc.
    checksum: str  # SHA-256 for deduplication

    # Position and context within document
    position_index: int = 0  # Order of appearance in document
    page_number: Optional[int] = None
    bounding_box: Optional[dict] = None  # {l, t, r, b} in Docling doc units

    # Extracted/generated metadata
    caption: Optional[str] = None  # From document or generated
    classification: Optional[str] = None  # Docling picture-classification label
    alt_text: Optional[str] = None
    description: Optional[str] = None  # Set by a vision model, if configured

    # Set after storage (artifact write)
    s3_uri: Optional[str] = None  # e.g. file://.../images/<id>.png, or a real S3 URI

    # Technical metadata
    width: Optional[int] = None
    height: Optional[int] = None
    size_bytes: int = 0

    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ImageDescription:
    """Result of describing an image via a vision-capable LLM — see
    ``ImageDescriptionPort``. Produced by the refinement layer
    (dataset/clean -> dataset/super_clean, see app.application.documents.
    refine_pipeline), independent of the extraction pipeline's transient
    ``ExtractedImage`` objects — refinement reads already-persisted image
    files, not in-memory pipeline state.
    """

    description: str
    category: str


@dataclass
class RawBinaryAsset:
    """
    Original raw binary data of a document before any processing.
    Used for data retention, audit trails, and potential reprocessing.
    """

    id: str  # UUID
    document_id: str  # FK to Document
    data: bytes  # Original binary content
    filename: str
    mime_type: str
    checksum: str  # SHA-256 hash for integrity verification and deduplication
    size_bytes: int
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
