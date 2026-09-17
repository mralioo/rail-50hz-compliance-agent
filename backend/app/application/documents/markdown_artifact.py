"""
Renders the final ``<rel_path>.md`` artifact: YAML frontmatter (the contract
``app.kb.project_corpus`` reads as its single source of truth for chunking
into the KB stores) + Markdown body with every ``<!-- image -->`` placeholder
replaced, in document order, by a link to the extracted image, followed by an
"Extracted images" reference table.

This is rail-project-specific rendering (not part of the ported reference
architecture) that sits on top of the generic ``WriteExtractedTextArtifactStep``.
"""
import re
from pathlib import Path

from app.domain.documents.models import Chunk, ExtractedImage

_SUBSTATION_RE = re.compile(r"^(ESTW|UZ)[\s_-]", re.IGNORECASE)
_IMAGE_PLACEHOLDER_RE = re.compile(r"<!--\s*image\s*-->", re.IGNORECASE)
_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_YAML_LINE_RE = re.compile(r'^(\w+):\s*(?:"((?:[^"\\]|\\.)*)"|(\S+))\s*$')


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Returns (fields, body). Hand-rolled to match exactly what
    ``frontmatter()``/``_yaml_str`` below write - not a general YAML parser,
    so no PyYAML dependency for this fixed, self-controlled schema. Shared by
    ``app.kb.project_corpus`` (KB chunking) and
    ``app.application.documents.refine_markdown`` (the refinement layer) —
    both read the same artifact contract this module writes."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fields: dict = {}
    for line in m.group(1).splitlines():
        lm = _YAML_LINE_RE.match(line)
        if not lm:
            continue
        key = lm.group(1)
        if lm.group(2) is not None:
            fields[key] = lm.group(2).replace('\\"', '"').replace("\\\\", "\\")
        else:
            raw = lm.group(3)
            fields[key] = None if raw == "null" else raw
    return fields, text[m.end():]


def _substation_for(rel_parts: tuple[str, ...]) -> str | None:
    for part in rel_parts:
        if _SUBSTATION_RE.match(part):
            return part
    return None


def _yaml_str(value: str) -> str:
    """Minimal YAML double-quoted scalar - matches the hand-rolled parser in
    app.kb.project_corpus (no PyYAML dependency on either side)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def frontmatter(
    *,
    project: str,
    rel_path: Path,
    source_path: Path,
    page_count: int | None,
    image_count: int,
    extra: dict[str, str] | None = None,
) -> str:
    rel_parts = rel_path.parts
    category = rel_path.parent.name if len(rel_parts) > 1 else ""
    substation = _substation_for(rel_parts) or ""
    lines = [
        "---",
        f"project: {_yaml_str(project)}",
        f"substation: {_yaml_str(substation)}",
        f"category: {_yaml_str(category)}",
        f"source_path: {_yaml_str(source_path.as_posix())}",
        "tier: 1",
        f"page_count: {page_count if page_count is not None else 'null'}",
        f"image_count: {image_count}",
    ]
    for key, value in (extra or {}).items():
        lines.append(f"{key}: {_yaml_str(value)}")
    lines += ["---", ""]
    return "\n".join(lines)


def assemble_body_text(chunks: list[Chunk]) -> str:
    """Sort chunks by first page number then index, join their text.

    Mirrors the reference architecture's WriteExtractedTextStep sort order.
    Docling emits chunks in document reading order, so this join also
    preserves the relative order of any ``<!-- image -->`` placeholders they
    contain — the ordering ``inline_image_links`` below depends on.
    """

    def _sort_key(chunk: Chunk) -> tuple:
        pages = chunk.metadata.get("page_numbers") or []
        first_page = pages[0] if pages else float("inf")
        return (first_page, chunk.index)

    sorted_chunks = sorted(chunks, key=_sort_key)
    return "\n\n".join(c.text for c in sorted_chunks if c.text)


def inline_image_links(text: str, links: dict[int, str]) -> str:
    """Replace each ``<!-- image -->`` placeholder, in order, with a link to
    the correspondingly-ordered extracted image.

    Docling emits one placeholder per picture in document order, so the k-th
    placeholder is picture index k. A picture skipped during extraction (too
    small / no bbox) has no link, so its placeholder is annotated instead of
    dropped, keeping the k -> picture-index alignment intact.
    """
    counter = {"i": -1}

    def repl(_m: re.Match) -> str:
        counter["i"] += 1
        link = links.get(counter["i"])
        if link is None:
            return "<!-- image (not extracted: too small or no bbox) -->"
        return f"![picture {counter['i']}]({link})"

    return _IMAGE_PLACEHOLDER_RE.sub(repl, text)


def images_reference_table(images: list[ExtractedImage], links: dict[int, str]) -> str:
    if not images:
        return ""
    lines = [
        "## Extracted images",
        "",
        "| # | page | file | type | caption |",
        "| - | ---- | ---- | ---- | ------- |",
    ]
    for img in images:
        link = links.get(img.position_index)
        page = img.page_number if img.page_number is not None else ""
        cls = img.classification or ""
        cap = (img.caption or "").replace("|", "\\|").replace("\n", " ")
        cell = f"[{link.rsplit('/', 1)[-1]}]({link})" if link else "(not extracted)"
        lines.append(f"| {img.position_index} | {page} | {cell} | {cls} | {cap} |")
    lines.append("")
    return "\n".join(lines)


def page_count_from(chunks: list[Chunk], images: list[ExtractedImage]) -> int | None:
    """Best-effort page count: DocumentConversionClientPort returns only chunks
    + images (no document metadata), so this approximates from the highest
    page number seen across either."""
    pages = [p for c in chunks for p in (c.metadata.get("page_numbers") or [])]
    pages += [img.page_number for img in images if img.page_number is not None]
    return max(pages) if pages else None
