"""OpenSearch-backed semantic (vector) retrieval over the project-document
corpus (dataset/clean/<project>/ or dataset/super_clean/<project>/ - see
app.kb.project_corpus, whose iter_chunks() is agnostic to which one it's
pointed at) - parallel to app.kb.opensearch_store (regulations), reusing its
connection/embedding primitives rather than duplicating them. Separate index
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
class ImageHit:
    file: str
    path: str
    category: str
    description: str


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
    images: list[ImageHit]


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
                    # Object (not nested): we only ever store/retrieve these
                    # whole, never query "category X AND description Y within
                    # the same sub-object" - object's flattened indexing is
                    # fine and avoids nested-query overhead. Resolved once at
                    # chunking time (app.kb.project_corpus._extract_images),
                    # so this *is* the artifact/vector-store tie-together -
                    # see docs/OPENSEARCH_NEO4J_EVALUATION.md §9.5.
                    "images": {
                        "type": "object",
                        "properties": {
                            "file": {"type": "keyword"},
                            "path": {"type": "keyword"},
                            "category": {"type": "keyword"},
                            "description": {"type": "text"},
                        },
                    },
                }
            },
        },
    )


def clear_project(project: str) -> int:
    """Delete every indexed chunk for *project*, so a re-ingest from a
    different source corpus (e.g. dataset/super_clean/ after dataset/clean/)
    can't leave stale orphan chunks behind — chunk_id is
    f"{project}:{doc_name}#{index}", so a doc whose refined heading structure
    produces *fewer* sections than before would otherwise leave its old
    higher-indexed chunks sitting in the index forever."""
    client = get_client()
    if not client.indices.exists(index=PROJECT_INDEX):
        return 0
    resp = client.delete_by_query(
        index=PROJECT_INDEX,
        body={"query": {"term": {"project": project}}},
        refresh=True,
    )
    return resp.get("deleted", 0)


def ingest(source_dir: Path, project: str, *, clear_existing: bool = True) -> int:
    """Chunk + embed + index every document under source_dir/project/ (either
    dataset/clean/ or dataset/super_clean/ - iter_chunks doesn't care which)."""
    chunks: list[ProjectChunk] = iter_chunks(source_dir, project)
    if not chunks:
        return 0
    ensure_index()
    if clear_existing:
        clear_project(project)
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
                "images": [
                    {"file": img.file, "path": img.path, "category": img.category, "description": img.description}
                    for img in c.images
                ],
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
    vector = embed([text], is_query=True)[0]
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
            images=[
                ImageHit(
                    file=img.get("file", ""),
                    path=img.get("path", ""),
                    category=img.get("category", ""),
                    description=img.get("description", ""),
                )
                for img in hit["_source"].get("images") or []
            ],
        )
        for hit in resp["hits"]["hits"]
    ]
