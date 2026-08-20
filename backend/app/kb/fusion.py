"""Hybrid fusion PoC: query OpenSearch (semantic) and Neo4j (fulltext +
graph relationships) together, merge/rank the results, and annotate any hit
that cites a deprecated code with what superseded it.

Standalone evaluation harness — not wired into routes.py/`/chat`. Run via
`backend/scripts/kb_compare.py` (`make kb-compare QUERY="..."`).
See docs/OPENSEARCH_NEO4J_EVALUATION.md.
"""
import re
import time
from dataclasses import dataclass, field

from app.kb import neo4j_store, opensearch_store

_CODE_RE = re.compile(r"\b[A-Za-z]+\s+\d[\d.\-]*\b")


@dataclass
class FusedResult:
    query: str
    semantic_hits: list[opensearch_store.OpenSearchHit] = field(default_factory=list)
    fulltext_hits: list[neo4j_store.SectionHit] = field(default_factory=list)
    graph_context: list[neo4j_store.CodeStatus] = field(default_factory=list)
    merged: list[str] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)


def _extract_codes(text: str) -> set[str]:
    return {m.strip() for m in _CODE_RE.findall(text)}


def compare(query: str, k: int = 5, kb_ids: list[str] | None = None) -> FusedResult:
    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    semantic_hits = opensearch_store.query(query, k=k, kb_ids=kb_ids)
    timings["os_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    t0 = time.perf_counter()
    fulltext_hits = neo4j_store.find_sections(query, kb_ids=kb_ids, limit=k)
    timings["neo4j_fulltext_ms"] = round((time.perf_counter() - t0) * 1000, 1)

    candidate_codes: set[str] = set()
    for hit in semantic_hits:
        candidate_codes |= _extract_codes(hit.text)
    for hit in fulltext_hits:
        candidate_codes |= _extract_codes(hit.text)

    t0 = time.perf_counter()
    graph_context = [
        status
        for code in sorted(candidate_codes)
        if (status := neo4j_store.code_status(code)) is not None
    ]
    timings["neo4j_status_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    timings["total_ms"] = round(sum(timings.values()), 1)

    deprecated = {s.code: s.superseded_by for s in graph_context if s.status == "deprecated"}

    seen: set[tuple[str, str]] = set()
    merged: list[str] = []
    for hit in list(semantic_hits) + [
        opensearch_store.OpenSearchHit(h.doc_name, h.heading, h.text, h.score, h.kb_id)
        for h in fulltext_hits
    ]:
        key = (hit.doc_name, hit.heading)
        if key in seen:
            continue
        seen.add(key)
        line = f"[{hit.doc_name}] {hit.heading or '(preamble)'}: {hit.text[:200]}"
        cited = _extract_codes(hit.text)
        for code in cited & deprecated.keys():
            replacement = deprecated[code] or "unknown"
            line += f"\n  [GRAPH WARNING] cites deprecated {code}, superseded by {replacement}"
        merged.append(line)

    return FusedResult(
        query=query,
        semantic_hits=semantic_hits,
        fulltext_hits=fulltext_hits,
        graph_context=graph_context,
        merged=merged,
        timings=timings,
    )
