"""Chunking for the project-document corpus (dataset/clean/<project>/ or
dataset/super_clean/<project>/, see app.application.documents.
dataset_ingestion_service / dataset_refinement_service) - parallel to
app.kb.corpus, which is regulation-specific (H2-only split, active_codes/
supersession regex tuned to that corpus's markdown convention and not
applicable here).

Project documents get real Markdown heading structure from the Docling
server (plus an "Extracted images" reference section) - so chunking here
splits on any heading level (`^#+ `), not just H2.

Storage strategy this module is the read side of (see
docs/OPENSEARCH_NEO4J_EVALUATION.md §9.5 for the full writeup): each chunk's
own image references (path + category/description, if its section is or
contains an "Extracted images" table) are resolved to a real filesystem path
*here*, once, at chunking time - not re-derived later from doc-level
filesystem globbing. This makes app.kb.project_opensearch_store's index the
single source of truth for "this chunk's text + vector + the images that
actually belong to it", so app.application.documents (the artifact store,
untouched by this module) and OpenSearch (the searchable/embeddable store)
each own exactly one job, and a downstream consumer (e.g. the Embedding Atlas
export) never needs to know which source corpus (clean/super_clean) or which
frontmatter table shape (clean's `type`/`caption` columns vs. super_clean's
`category`/`description` columns) a chunk came from.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.application.documents.markdown_artifact import parse_frontmatter

_HEADING_RE = re.compile(r"^(#+)\s+(.*)$", re.MULTILINE)
_TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$", re.MULTILINE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff")


@dataclass
class ImageRef:
    """One image belonging to a specific chunk, resolved to a real path on
    disk (images physically live under dataset/clean/.../images/ - never
    duplicated into dataset/super_clean/, see app.application.documents.
    local_keys - so this resolution has to happen relative to whichever .md
    file the link was actually written in)."""

    file: str  # filename only, e.g. "000_p001_a700b2a3.png"
    path: str  # absolute filesystem path, resolved from the chunk's own .md location
    category: str = ""  # Docling's coarse classification, or the refinement layer's LLM category
    description: str = ""  # caption (clean) or LLM description (super_clean); "" if neither


@dataclass
class ProjectChunk:
    project: str
    substation: str
    category: str
    source_path: str
    tier: int
    doc_name: str  # relative path under the project, e.g. "ESTW-A Dörstewitz/Erdungsanlage/2333116242_Info.md"
    heading: str  # "" for the section before the first heading
    text: str
    chunk_id: str  # f"{project}:{doc_name}#{index}"
    images: list[ImageRef] = field(default_factory=list)


def _split_by_heading(body: str) -> list[tuple[str, str]]:
    """[(heading, text), ...] - "" heading for any text before the first
    "^#+ " line. Every heading level is treated as a split point (unlike
    app.kb.corpus's H2-only rule) since Tier-1 Docling output nests real
    document structure that a flat H2 split would either miss or merge."""
    matches = list(_HEADING_RE.finditer(body))
    if not matches:
        return [("", body.strip())] if body.strip() else []
    sections = []
    if matches[0].start() > 0:
        preamble = body[: matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        heading = m.group(2).strip()
        text = body[start:end].strip()
        if text:
            sections.append((heading, text))
    return sections


def _extract_images(text: str, md_path: Path) -> list[ImageRef]:
    """Find every "| ... | [file.png](link) | col_a | col_b |" table row in
    this chunk's text and resolve it to an ImageRef. Handles both the
    extraction layer's table (`| # | page | file | type | caption |`) and the
    refinement layer's (`| # | file | category | description |`) without
    caring which one it is: whatever trailing columns follow the image link
    become category/description positionally. Table header/separator rows
    naturally don't match (no real `[text](link)` in them)."""
    images: list[ImageRef] = []
    for row_match in _TABLE_ROW_RE.finditer(text):
        cells = [c.strip() for c in row_match.group(1).split("|")]
        link_idx = None
        file_name = link_target = None
        for i, cell in enumerate(cells):
            link_match = _MD_LINK_RE.search(cell)
            if link_match and link_match.group(2).lower().endswith(_IMAGE_SUFFIXES):
                link_idx, file_name, link_target = i, link_match.group(1), link_match.group(2)
                break
        if link_idx is None:
            continue
        trailing = cells[link_idx + 1 :]
        category = trailing[0] if len(trailing) >= 1 else ""
        description = trailing[1] if len(trailing) >= 2 else ""
        resolved = (md_path.parent / link_target).resolve()
        images.append(
            ImageRef(file=file_name, path=str(resolved), category=category, description=description)
        )
    return images


def iter_chunks(source_dir: Path, project: str) -> list[ProjectChunk]:
    project_dir = source_dir / project
    chunks: list[ProjectChunk] = []
    for path in sorted(project_dir.rglob("*.md")):
        if path.name == "_manifest.json":
            continue
        fields, body = parse_frontmatter(path.read_text())
        if not fields:
            continue  # not a docling_pipeline output (e.g. a stray file)
        doc_name = path.relative_to(project_dir).as_posix()
        for i, (heading, text) in enumerate(_split_by_heading(body)):
            chunks.append(
                ProjectChunk(
                    project=fields.get("project", project),
                    substation=fields.get("substation") or "",
                    category=fields.get("category") or "",
                    source_path=fields.get("source_path", ""),
                    tier=int(fields.get("tier") or 0),
                    doc_name=doc_name,
                    heading=heading,
                    text=text,
                    chunk_id=f"{project}:{doc_name}#{i}",
                    images=_extract_images(text, path),
                )
            )
    return chunks
