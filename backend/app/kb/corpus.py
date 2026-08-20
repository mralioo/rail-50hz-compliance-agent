"""Shared corpus chunking for the OpenSearch/Neo4j evaluation harness.

Reuses `app.agent.rag`'s existing folder walk and section-split logic rather
than reimplementing it, so both new stores chunk the corpus identically to
the keyword baseline (`rag.retrieve()`) — any relevance differences the
comparison doc reports are attributable to retrieval method, not chunking.

See docs/OPENSEARCH_NEO4J_EVALUATION.md.
"""
import re
from dataclasses import dataclass

from app.agent.rag import RULE_LINE_RE, _read_corpus, list_knowledge_bases  # noqa: F401


@dataclass
class Chunk:
    kb_id: str
    doc_name: str
    heading: str  # "" for the preamble chunk before the first "## "
    text: str
    chunk_id: str  # f"{kb_id}:{doc_name}#{index}"


def _kb_id_for(doc_name: str, kb_ids: list[str] | None) -> str:
    """Resolve which KB a filename belongs to by re-checking against
    list_knowledge_bases()'s own folder convention (general = top-level,
    else the owning subdirectory's lowercased name)."""
    from app.core.config import get_settings

    regs_dir = get_settings().regulations_dir
    for sub in sorted(p for p in regs_dir.iterdir() if p.is_dir()) if regs_dir.exists() else []:
        if (sub / doc_name).exists():
            return sub.name.lower()
    return "general"


def iter_chunks(kb_ids: list[str] | None = None) -> list[Chunk]:
    """Same `"\\n## "` H2-section split `rag.retrieve()` uses, kb_id-tagged
    and structured for indexing into OpenSearch/Neo4j."""
    chunks: list[Chunk] = []
    for doc_name, text in _read_corpus(kb_ids):
        kb_id = _kb_id_for(doc_name, kb_ids)
        sections = text.split("\n## ")
        for i, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue
            if i == 0:
                heading = ""
            else:
                heading, _, section = section.partition("\n")
            chunks.append(
                Chunk(
                    kb_id=kb_id,
                    doc_name=doc_name,
                    heading=heading.strip(),
                    text=section.strip(),
                    chunk_id=f"{kb_id}:{doc_name}#{i}",
                )
            )
    return chunks


_CODE = r"[A-Za-z]+\s+\d[\d.\-]*"
SUPERSEDED_RE = re.compile(
    rf"({_CODE}),?\s+superseded\s+\d{{4}}\s+by\s+({_CODE})",
    re.IGNORECASE,
)


def extract_supersessions(text: str) -> list[tuple[str, str]]:
    """Pull (old_code, new_code) pairs out of corpus prose, e.g. the real
    sentence in db_ril_954_9101.md's "4.5 Documentation" section:
    "**Ril 954.0107**, superseded 2021 by Ril 954.9101". Markdown emphasis
    markers are stripped first since they'd otherwise break the code-name
    match (e.g. "**Ril 954.0107**")."""
    plain = text.replace("*", "").replace("\n", " ")
    return [(old.strip(), new.strip()) for old, new in SUPERSEDED_RE.findall(plain)]
