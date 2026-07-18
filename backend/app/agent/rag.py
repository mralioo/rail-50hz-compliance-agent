"""Minimal RAG over the mock DB Ril corpus in `backend/data/regulations/`.

Two access paths:
- `load_rules()`  — parses the machine-readable limit blocks (used by the
  mock agent for deterministic checks).
- `retrieve()`   — naive keyword retrieval of prose sections (used to ground
  the Vertex agent prompt). Swap for Vertex AI Search / embeddings later.
"""
import re
from dataclasses import dataclass, field

from app.core.config import get_settings

RULE_LINE_RE = re.compile(r"^(\w+):\s*(.+)$", re.MULTILINE)


@dataclass
class RuleSet:
    min_bending_radius_mm: float = 150.0
    max_pulling_force_n: float = 500.0
    active_codes: list[str] = field(default_factory=list)
    deprecated_codes: list[str] = field(default_factory=list)


def _read_corpus() -> list[tuple[str, str]]:
    regs_dir = get_settings().regulations_dir
    return [(p.name, p.read_text(encoding="utf-8")) for p in sorted(regs_dir.glob("*.md"))]


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


def retrieve(query: str, k: int = 3) -> list[str]:
    terms = {t.lower() for t in re.findall(r"\w{3,}", query)}
    sections: list[tuple[int, str]] = []
    for name, text in _read_corpus():
        for section in text.split("\n## "):
            score = sum(1 for t in terms if t in section.lower())
            if score:
                sections.append((score, f"[{name}] {section.strip()}"))
    sections.sort(key=lambda s: s[0], reverse=True)
    return [s for _, s in sections[:k]]
