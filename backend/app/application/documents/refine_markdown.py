"""Renders the `dataset/super_clean/<project>/<rel_path>.md` artifact: same
frontmatter contract as `markdown_artifact.py` (plus a `refinement_model`
field) with an LLM-cleaned body and each image's inline placeholder replaced
by its LLM description (not just a bare link) — a plain markdown image link
contributes nothing to a text embedding, but a sentence describing what the
drawing shows does, which is the whole point of this layer (see
docs/DOCUMENT_EXTRACTION.md's refinement-layer section).

Two-pass, mirroring the extraction layer's own placeholder convention:
1. Before cleanup, convert each existing ``![picture N](...)`` link back to a
   ``<!-- image N -->`` marker (an LLM cleanup pass must not be trusted to
   preserve markdown link syntax verbatim - it may "fix" it as if it were
   noise) and instruct the model to preserve the markers exactly.
2. After cleanup, replace each surviving marker with the image's description
   + a link back to the original file (still stored under dataset/clean/,
   not duplicated).
"""
import os
import re
from pathlib import Path

from app.domain.documents.models import ImageDescription

_IMAGE_LINK_RE = re.compile(r"!\[picture (\d+)\]\([^)]*\)")
_IMAGE_MARKER_RE = re.compile(r"<!--\s*image\s+(\d+)\s*-->", re.IGNORECASE)


def markers_from_links(text: str) -> str:
    """``![picture N](...)`` -> ``<!-- image N -->``, so the index survives
    an LLM cleanup pass as an explicit, instructed-to-preserve marker instead
    of markdown link syntax the model might otherwise "clean" away."""
    return _IMAGE_LINK_RE.sub(lambda m: f"<!-- image {m.group(1)} -->", text)


def inline_descriptions(
    text: str,
    descriptions: dict[int, ImageDescription],
    links: dict[int, str],
) -> str:
    """Replace each ``<!-- image N -->`` marker with its description (falls
    back to noting the image if description/link generation failed for that
    index, same fail-open spirit as the extraction layer's placeholder
    handling — one bad image must not break the rest of the document)."""

    def repl(m: re.Match) -> str:
        idx = int(m.group(1))
        desc = descriptions.get(idx)
        link = links.get(idx)
        if desc is None:
            return f"<!-- image {idx} (no description available) -->"
        text_part = f"[Figure {idx} — {desc.category}] {desc.description}"
        return f"{text_part} ({link})" if link else text_part

    return _IMAGE_MARKER_RE.sub(repl, text)


def relative_image_link(super_clean_md_path: Path, clean_image_path: Path) -> str:
    """Relative link from the super_clean .md file's directory back to the
    original image under dataset/clean/ (images are not duplicated into
    dataset/super_clean/)."""
    return os.path.relpath(clean_image_path, start=super_clean_md_path.parent)


def images_reference_table(
    image_paths: list[Path],
    descriptions: dict[int, ImageDescription],
    links: dict[int, str],
) -> str:
    if not image_paths:
        return ""
    lines = [
        "## Extracted images",
        "",
        "| # | file | category | description |",
        "| - | ---- | -------- | ----------- |",
    ]
    for idx, path in enumerate(image_paths):
        link = links.get(idx, path.name)
        desc = descriptions.get(idx)
        category = desc.category if desc else ""
        description = (desc.description if desc else "").replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {idx} | [{path.name}]({link}) | {category} | {description} |")
    lines.append("")
    return "\n".join(lines)
