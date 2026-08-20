"""Chunking for the project-document corpus (dataset/clean/<project>/,
produced by app.ingestion.docling_pipeline) - parallel to app.kb.corpus,
which is regulation-specific (H2-only split, active_codes/supersession
regex tuned to that corpus's markdown convention and not applicable here).

Project documents get real Markdown heading structure from Docling (Tier 1)
or are a single fenced-code stub (Tier 2, see docling_pipeline.convert_tier2)
- so chunking here splits on any heading level (`^#+ `), not just H2.
"""
import re
from dataclasses import dataclass
from pathlib import Path

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_YAML_LINE_RE = re.compile(r'^(\w+):\s*(?:"((?:[^"\\]|\\.)*)"|(\S+))\s*$')
_HEADING_RE = re.compile(r"^(#+)\s+(.*)$", re.MULTILINE)


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


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Returns (fields, body). Hand-rolled to match exactly what
    docling_pipeline._frontmatter/_yaml_str write - not a general YAML
    parser, so no PyYAML dependency for this fixed, self-controlled schema."""
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


def iter_chunks(clean_dir: Path, project: str) -> list[ProjectChunk]:
    project_dir = clean_dir / project
    chunks: list[ProjectChunk] = []
    for path in sorted(project_dir.rglob("*.md")):
        if path.name == "_manifest.json":
            continue
        fields, body = _parse_frontmatter(path.read_text())
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
                )
            )
    return chunks
