"""OpenSearch-backed semantic (vector) retrieval over the project-document
corpus (dataset/clean/<project>/, see app.kb.project_corpus) - parallel to
app.kb.opensearch_store (regulations), reusing its connection/embedding
primitives rather than duplicating them. Separate index
(`rail50hz_project_docs`) so this never collides with the regulation index.

Evaluation-harness backend, same status as opensearch_store.py - not wired
into routes.py/chat. See docs/OPENSEARCH_NEO4J_EVALUATION.md.
"""
from dataclasses import dataclass
from pathlib import Path

from opensearchpy import helpers

from app.kb.opensearch_store import embed, embed_dims, get_client
from app.kb.project_corpus import ProjectChunk, iter_chunks

PROJECT_INDEX = "rail50hz_project_docs"


@dataclass
class ProjectHit:
    doc_name: str
    heading: str
    text: str
    score: float
    project: str
    substation: str
    category: str
    source_path: str


def ensure_index(dims: int | None = None) -> None:
    client = get_client()
    dims = dims or embed_dims()
    if client.indices.exists(index=PROJECT_INDEX):
        return
    client.indices.create(
        index=PROJECT_INDEX,
        body={
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "project": {"type": "keyword"},
                    "substation": {"type": "keyword"},
                    "category": {"type": "keyword"},
                    "source_path": {"type": "keyword"},
                    "doc_name": {"type": "keyword"},
                    "heading": {"type": "text"},
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": dims,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                        },
                    },
                }
            },
        },
    )


def ingest(clean_dir: Path, project: str) -> int:
    chunks: list[ProjectChunk] = iter_chunks(clean_dir, project)
    if not chunks:
        return 0
    ensure_index()
    vectors = embed([c.text for c in chunks])
    actions = [
        {
            "_index": PROJECT_INDEX,
            "_id": c.chunk_id,
            "_source": {
                "project": c.project,
                "substation": c.substation,
                "category": c.category,
                "source_path": c.source_path,
                "doc_name": c.doc_name,
                "heading": c.heading,
                "text": c.text,
                "embedding": vec,
            },
        }
        for c, vec in zip(chunks, vectors)
    ]
    helpers.bulk(get_client(), actions)
    get_client().indices.refresh(index=PROJECT_INDEX)
    return len(actions)


def query(
    text: str,
    k: int = 5,
    substation: str | None = None,
    category: str | None = None,
) -> list[ProjectHit]:
    vector = embed([text])[0]
    knn_clause = {"knn": {"embedding": {"vector": vector, "k": k}}}
    filters = []
    if substation:
        filters.append({"term": {"substation": substation}})
    if category:
        filters.append({"term": {"category": category}})
    body: dict = {"size": k, "query": knn_clause}
    if filters:
        body["query"] = {"bool": {"must": [knn_clause], "filter": filters}}
    resp = get_client().search(index=PROJECT_INDEX, body=body)
    return [
        ProjectHit(
            doc_name=hit["_source"]["doc_name"],
            heading=hit["_source"]["heading"],
            text=hit["_source"]["text"],
            score=hit["_score"],
            project=hit["_source"]["project"],
            substation=hit["_source"]["substation"],
            category=hit["_source"]["category"],
            source_path=hit["_source"]["source_path"],
        )
        for hit in resp["hits"]["hits"]
    ]
