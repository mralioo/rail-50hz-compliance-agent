"""Neo4j-backed graph retrieval over the regulation corpus — models the
explicit relationships a vector/keyword index can't: which codes are active,
which are deprecated, and what superseded them.

Schema:
    (:KnowledgeBase {id, name})
    (:Document {id, name, kb_id})-[:IN_KB]->(:KnowledgeBase)
    (:Document)-[:HAS_SECTION]->(:Section {id, heading, text})
    (:Code {code, status: "active"|"deprecated"})
    (:Document)-[:CITES]->(:Code)
    (:Code)-[:SUPERSEDED_BY]->(:Code)

Forward reference, not built this iteration: a future
`(:Finding)-[:CITES]->(:Code)` edge is exactly what would give
`Finding.regulation` (a flat string today, schemas.py) a structured link —
see docs/OPENSEARCH_NEO4J_EVALUATION.md.

Evaluation-harness backend, parallel to `app.agent.rag` — not wired into
`routes.py`/`/chat`.
"""
import re
from dataclasses import dataclass

from neo4j import GraphDatabase

from app.agent.rag import list_knowledge_bases
from app.core.config import get_settings
from app.kb.corpus import RULE_LINE_RE, extract_supersessions, iter_chunks


@dataclass
class SectionHit:
    doc_name: str
    heading: str
    text: str
    score: float
    kb_id: str


@dataclass
class CodeStatus:
    code: str
    status: str  # "active" | "deprecated" | "unknown"
    superseded_by: str | None = None


def get_driver():
    settings = get_settings()
    return GraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )


def _ensure_fulltext_index(session) -> None:
    session.run(
        "CREATE FULLTEXT INDEX sectionFulltext IF NOT EXISTS "
        "FOR (s:Section) ON EACH [s.heading, s.text]"
    )


def ingest(kb_ids: list[str] | None = None) -> int:
    chunks = iter_chunks(kb_ids)
    if not chunks:
        return 0

    kb_names = {kb.id: kb.name for kb in list_knowledge_bases()}

    with get_driver() as driver, driver.session() as session:
        _ensure_fulltext_index(session)
        for c in chunks:
            session.run(
                "MERGE (kb:KnowledgeBase {id:$kb_id}) SET kb.name=$kb_name",
                kb_id=c.kb_id,
                kb_name=kb_names.get(c.kb_id, c.kb_id),
            )
            doc_id = f"{c.kb_id}:{c.doc_name}"
            session.run(
                "MERGE (d:Document {id:$doc_id}) SET d.name=$doc_name, d.kb_id=$kb_id "
                "MERGE (kb:KnowledgeBase {id:$kb_id}) "
                "MERGE (d)-[:IN_KB]->(kb)",
                doc_id=doc_id,
                doc_name=c.doc_name,
                kb_id=c.kb_id,
            )
            session.run(
                "MATCH (d:Document {id:$doc_id}) "
                "MERGE (s:Section {id:$section_id}) "
                "SET s.heading=$heading, s.text=$text "
                "MERGE (d)-[:HAS_SECTION]->(s)",
                doc_id=doc_id,
                section_id=c.chunk_id,
                heading=c.heading,
                text=c.text,
            )

            # Scan every chunk (not just the preamble) for the fenced
            # active_codes/deprecated_codes block — it lives wherever the
            # corpus author put it (today: the "Machine-readable limits"
            # H2 section). MERGE below is idempotent, so no per-doc gating
            # is needed to avoid duplicates.
            for key, value in RULE_LINE_RE.findall(c.text):
                if key == "active_codes":
                    for code in [x.strip() for x in value.split(",") if x.strip()]:
                        session.run(
                            "MERGE (code:Code {code:$code}) "
                            "SET code.status = coalesce(code.status, 'active') "
                            "WITH code "
                            "MATCH (d:Document {id:$doc_id}) "
                            "MERGE (d)-[:CITES]->(code)",
                            code=code,
                            doc_id=doc_id,
                        )
                elif key == "deprecated_codes":
                    for code in [x.strip() for x in value.split(",") if x.strip()]:
                        session.run(
                            "MERGE (code:Code {code:$code}) SET code.status='deprecated' "
                            "WITH code "
                            "MATCH (d:Document {id:$doc_id}) "
                            "MERGE (d)-[:CITES]->(code)",
                            code=code,
                            doc_id=doc_id,
                        )

            for old_code, new_code in extract_supersessions(c.text):
                session.run(
                    "MERGE (old:Code {code:$old_code}) "
                    "SET old.status = coalesce(old.status, 'deprecated') "
                    "MERGE (new:Code {code:$new_code}) "
                    "SET new.status = coalesce(new.status, 'active') "
                    "MERGE (old)-[:SUPERSEDED_BY]->(new)",
                    old_code=old_code,
                    new_code=new_code,
                )

    return len(chunks)


def find_sections(query: str, kb_ids: list[str] | None = None, limit: int = 5) -> list[SectionHit]:
    with get_driver() as driver, driver.session() as session:
        # Lucene fulltext syntax: OR together the individual terms so a
        # multi-word query still matches sections containing any of them
        # (a plain phrase query would require an exact substring match).
        lucene_query = " OR ".join(re.findall(r"\w+", query)) or query
        result = session.run(
            "CALL db.index.fulltext.queryNodes('sectionFulltext', $search_text) "
            "YIELD node, score "
            "MATCH (d:Document)-[:HAS_SECTION]->(node) "
            "WHERE $kb_ids IS NULL OR d.kb_id IN $kb_ids "
            "RETURN d.name AS doc_name, d.kb_id AS kb_id, node.heading AS heading, "
            "node.text AS text, score "
            "ORDER BY score DESC LIMIT $limit",
            search_text=lucene_query,
            kb_ids=kb_ids,
            limit=limit,
        )
        return [
            SectionHit(
                doc_name=r["doc_name"],
                heading=r["heading"] or "",
                text=r["text"],
                score=r["score"],
                kb_id=r["kb_id"],
            )
            for r in result
        ]


def code_status(code: str) -> CodeStatus | None:
    """Walks the SUPERSEDED_BY chain to answer: is this code still valid,
    and if not, what replaced it? The graph-only capability a vector/keyword
    index cannot express."""
    with get_driver() as driver, driver.session() as session:
        result = session.run(
            "MATCH (c:Code {code:$code}) "
            "OPTIONAL MATCH path = (c)-[:SUPERSEDED_BY*0..5]->(latest) "
            "WHERE NOT (latest)-[:SUPERSEDED_BY]->() "
            "RETURN c.status AS status, latest.code AS latest_code "
            "ORDER BY length(path) DESC LIMIT 1",
            code=code,
        )
        record = result.single()
        if record is None:
            return None
        latest = record["latest_code"]
        return CodeStatus(
            code=code,
            status=record["status"] or "unknown",
            superseded_by=latest if latest and latest != code else None,
        )
