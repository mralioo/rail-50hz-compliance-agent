"""Minimal RAG over the mock DB Ril corpus in `backend/data/regulations/`.

Two access paths:
- `load_rules()`  — parses the machine-readable limit blocks (used by the
  mock agent for deterministic checks). Always reads the full corpus —
  ingest-time analysis is not user-filterable.
- `retrieve()`   — naive keyword retrieval of prose sections (used to ground
  the Vertex agent prompt). Swap for Vertex AI Search / embeddings later.
  Accepts `kb_ids` so the interactive chat path can scope grounding to an
  engineer-selected subset of knowledge bases (see `list_knowledge_bases()`).

A "knowledge base" is a directory-based grouping: loose top-level `*.md`
files under `regulations_dir` form the `general` KB; each immediate
subdirectory is its own KB keyed by its lowercased name. This is a live
filesystem view (not cached), so dropping a file into a KB directory takes
effect on the next request.
"""
import re
from dataclasses import dataclass, field

from app.core.config import get_settings
from app.models.schemas import KnowledgeBase

RULE_LINE_RE = re.compile(r"^(\w+):\s*(.+)$", re.MULTILINE)


@dataclass
class RuleSet:
    min_bending_radius_mm: float = 150.0
    max_pulling_force_n: float = 500.0
    active_codes: list[str] = field(default_factory=list)
    deprecated_codes: list[str] = field(default_factory=list)


def list_knowledge_bases() -> list[KnowledgeBase]:
    regs_dir = get_settings().regulations_dir
    if not regs_dir.exists():
        return [KnowledgeBase(id="general", name="General", doc_count=0)]
    kbs = [
        KnowledgeBase(
            id="general", name="General", doc_count=len(list(regs_dir.glob("*.md")))
        )
    ]
    for sub in sorted(p for p in regs_dir.iterdir() if p.is_dir()):
        kbs.append(
            KnowledgeBase(
                id=sub.name.lower(), name=sub.name, doc_count=len(list(sub.glob("*.md")))
            )
        )
    return kbs


def _read_corpus(kb_ids: list[str] | None = None) -> list[tuple[str, str]]:
    regs_dir = get_settings().regulations_dir
    wanted = set(kb_ids) if kb_ids else None

    files: list[tuple[str, str]] = []
    if not regs_dir.exists():
        return files
    if wanted is None or "general" in wanted:
        files += [(p.name, p.read_text(encoding="utf-8")) for p in sorted(regs_dir.glob("*.md"))]
    for sub in sorted(p for p in regs_dir.iterdir() if p.is_dir()):
        if wanted is None or sub.name.lower() in wanted:
            files += [(p.name, p.read_text(encoding="utf-8")) for p in sorted(sub.glob("*.md"))]
    return files


def load_rules() -> RuleSet:
    rules = RuleSet()
    for _, text in _read_corpus():
        for key, value in RULE_LINE_RE.findall(text):
            if key == "min_cable_bending_radius_mm":
                rules.min_bending_radius_mm = float(value)
            elif key == "max_cable_pulling_force_n":
                rules.max_pulling_force_n = float(value)
            elif key == "active_codes":
                rules.active_codes = [c.strip() for c in value.split(",")]
            elif key == "deprecated_codes":
                rules.deprecated_codes = [c.strip() for c in value.split(",")]
    return rules


def retrieve(query: str, k: int = 3, kb_ids: list[str] | None = None) -> list[str]:
    terms = {t.lower() for t in re.findall(r"\w{3,}", query)}
    sections: list[tuple[int, str]] = []
    for name, text in _read_corpus(kb_ids):
        for section in text.split("\n## "):
            score = sum(1 for t in terms if t in section.lower())
            if score:
                sections.append((score, f"[{name}] {section.strip()}"))
    sections.sort(key=lambda s: s[0], reverse=True)
    return [s for _, s in sections[:k]]
