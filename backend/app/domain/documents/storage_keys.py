"""
Pure functions for building storage object keys.

These keys define the path layout inside the storage backend (S3 bucket,
Garage, local filesystem, etc.) — ported from the reference architecture's
generic S3-style convention. Kept available for a future S3/Postgres-backed
deployment; the current local ingestion pipeline
(application/documents/local_keys.py) uses a source-path-mirroring
convention instead, for human-browsable output under dataset/clean/.

Convention:
    projects/{project_id}/documents/{document_id}/raw/{filename}
    projects/{project_id}/documents/{document_id}/images/{image_id}.bin
"""


def raw_document_key(project_id: str, document_id: str, filename: str) -> str:
    """Key for the original uploaded file."""
    return f"projects/{project_id}/documents/{document_id}/raw/{filename}"


def extracted_image_key(project_id: str, document_id: str, image_id: str) -> str:
    """Key for a single extracted image."""
    return f"projects/{project_id}/documents/{document_id}/images/{image_id}.bin"


def extracted_text_key(project_id: str, document_id: str) -> str:
    """Key for the extracted text file."""
    return f"projects/{project_id}/documents/{document_id}/extracted-text.txt"


def document_prefix(project_id: str, document_id: str) -> str:
    """Prefix covering all objects for one document."""
    return f"projects/{project_id}/documents/{document_id}/"


def project_prefix(project_id: str) -> str:
    """Prefix covering all objects for one project."""
    return f"projects/{project_id}/"
