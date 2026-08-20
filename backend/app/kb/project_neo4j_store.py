"""Neo4j-backed graph over the project-document corpus - turns the folder
taxonomy the client already uses (substation x document category) into real
one-hop graph queries, e.g. "every Erdungsanlage section for ESTW-A
Dörstewitz", the way app.kb.neo4j_store's code_status() does for regulation
supersession chains.

Schema (additive - different labels, same Neo4j instance as the regulation
graph in app.kb.neo4j_store, no interaction between the two):
    (:Project {id})
    (:Substation {name, project_id})-[:PART_OF]->(:Project)
    (:Document {id, name, category, tier, source_path})-[:BELONGS_TO]->(:Substation)
    (:Document)-[:HAS_SECTION]->(:Section {id, heading, text})

Evaluation-harness backend, same status as neo4j_store.py - not wired into
routes.py/chat. See docs/OPENSEARCH_NEO4J_EVALUATION.md.
"""
import re
from dataclasses import dataclass
from pathlib import Path

from app.kb.neo4j_store import get_driver
from app.kb.project_corpus import iter_chunks


@dataclass
class ProjectSectionHit:
    doc_name: str
    substation: str
    category: str
    heading: str
    text: str
    score: float


def _ensure_fulltext_index(session) -> None:
    session.run(
        "CREATE FULLTEXT INDEX projectSectionFulltext IF NOT EXISTS "
        "FOR (s:Section) ON EACH [s.heading, s.text]"
    )


def ingest(clean_dir: Path, project: str) -> int:
    chunks = iter_chunks(clean_dir, project)
    if not chunks:
        return 0

    with get_driver() as driver, driver.session() as session:
        _ensure_fulltext_index(session)
        session.run("MERGE (:Project {id:$project})", project=project)

        seen_docs: set[str] = set()
        for c in chunks:
            substation = c.substation or "(unassigned)"
            session.run(
                "MERGE (s:Substation {name:$name, project_id:$project}) "
                "WITH s MATCH (p:Project {id:$project}) MERGE (s)-[:PART_OF]->(p)",
                name=substation,
                project=c.project,
            )
            doc_id = f"{c.project}:{c.doc_name}"
            if doc_id not in seen_docs:
                session.run(
                    "MERGE (d:Document {id:$doc_id}) "
                    "SET d.name=$doc_name, d.category=$category, d.tier=$tier, "
                    "    d.source_path=$source_path "
                    "WITH d MATCH (s:Substation {name:$substation, project_id:$project}) "
                    "MERGE (d)-[:BELONGS_TO]->(s)",
                    doc_id=doc_id,
                    doc_name=c.doc_name,
                    category=c.category,
                    tier=c.tier,
                    source_path=c.source_path,
                    substation=substation,
                    project=c.project,
                )
                seen_docs.add(doc_id)
            session.run(
                "MATCH (d:Document {id:$doc_id}) "
                "MERGE (sec:Section {id:$section_id}) "
                "SET sec.heading=$heading, sec.text=$text "
                "MERGE (d)-[:HAS_SECTION]->(sec)",
                doc_id=doc_id,
                section_id=c.chunk_id,
                heading=c.heading,
                text=c.text,
            )

    return len(chunks)


def find_sections(
    query: str,
    project: str | None = None,
    substation: str | None = None,
    category: str | None = None,
    limit: int = 5,
) -> list[ProjectSectionHit]:
    with get_driver() as driver, driver.session() as session:
        lucene_query = " OR ".join(re.findall(r"\w+", query)) or query
        result = session.run(
            "CALL db.index.fulltext.queryNodes('projectSectionFulltext', $search_text) "
            "YIELD node, score "
            "MATCH (d:Document)-[:HAS_SECTION]->(node) "
            "MATCH (d)-[:BELONGS_TO]->(s:Substation) "
            "MATCH (s)-[:PART_OF]->(p:Project) "
            "WHERE ($project IS NULL OR p.id = $project) "
            "  AND ($substation IS NULL OR s.name = $substation) "
            "  AND ($category IS NULL OR d.category = $category) "
            "RETURN d.name AS doc_name, s.name AS substation, d.category AS category, "
            "node.heading AS heading, node.text AS text, score "
            "ORDER BY score DESC LIMIT $limit",
            search_text=lucene_query,
            project=project,
            substation=substation,
            category=category,
            limit=limit,
        )
        return [
            ProjectSectionHit(
                doc_name=r["doc_name"],
                substation=r["substation"] or "",
                category=r["category"] or "",
                heading=r["heading"] or "",
                text=r["text"],
                score=r["score"],
            )
            for r in result
        ]
