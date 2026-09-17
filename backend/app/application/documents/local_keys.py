"""
Local artifact key layout for the dataset ingestion pipeline.

Distinct from ``domain/data/documents/storage_keys.py`` (the reference
architecture's generic S3-style ``projects/{id}/documents/{id}/...``
convention, kept for a future S3/Postgres deployment): this project has no
document database, so documents are identified by their *source-relative
path* rather than a minted UUID, and artifacts are laid out to mirror
dataset/raw/ under dataset/clean/ for human browsability:

    <rel_path>.md                                 extracted text artifact
    <rel_path>/raw/<filename>                      raw binary artifact
    <rel_path>/images/<NNN>_p<PP>_<sha8>.png        extracted images

``rel_path`` is the source file's path relative to the project's raw root,
without its suffix (e.g. "ESTW-A Dörstewitz/Erdungsanlage/2333116242_Info").
"""
from pathlib import Path

from app.domain.documents.models import ExtractedImage


def text_key(rel_path: Path) -> str:
    return f"{rel_path.as_posix()}.md"


def raw_key(rel_path: Path, filename: str) -> str:
    return f"{rel_path.as_posix()}/raw/{filename}"


def image_filename(image: ExtractedImage) -> str:
    page = f"p{image.page_number:03d}" if image.page_number is not None else "pXXX"
    return f"{image.position_index:03d}_{page}_{image.checksum[:8]}.png"


def image_key(rel_path: Path, image: ExtractedImage) -> str:
    return f"{rel_path.as_posix()}/images/{image_filename(image)}"


def image_link_from_text_artifact(rel_path: Path, image: ExtractedImage) -> str:
    """Relative link from ``<rel_path>.md`` to the image, for use inside that
    markdown file (both live under the same parent directory)."""
    return f"{rel_path.name}/images/{image_filename(image)}"
