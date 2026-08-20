"""OpenSearch-backed semantic (vector) retrieval over the regulation corpus.

Evaluation-harness backend, parallel to `app.agent.rag`'s keyword search —
not wired into `routes.py`/`/chat`. See docs/OPENSEARCH_NEO4J_EVALUATION.md.

Embeddings default to a local, free `sentence-transformers` model so the PoC
needs no API key; set OPENSEARCH_EMBEDDING_PROVIDER=openai to use OpenAI's
`text-embedding-3-small` instead (reuses the existing OPENAI_API_KEY).
"""
from dataclasses import dataclass
from functools import lru_cache

from opensearchpy import OpenSearch, helpers

from app.core.config import get_settings
from app.kb.corpus import Chunk, iter_chunks

_LOCAL_MODEL_NAME = "all-MiniLM-L6-v2"
_LOCAL_DIMS = 384
_OPENAI_MODEL = "text-embedding-3-small"
_OPENAI_DIMS = 1536


@dataclass
class OpenSearchHit:
    doc_name: str
    heading: str
    text: str
    score: float
    kb_id: str


def get_client() -> OpenSearch:
    settings = get_settings()
    return OpenSearch(hosts=[settings.opensearch_host])


@lru_cache
def _local_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(_LOCAL_MODEL_NAME)


def embed_dims() -> int:
    provider = get_settings().opensearch_embedding_provider
    return _OPENAI_DIMS if provider == "openai" else _LOCAL_DIMS


def embed(texts: list[str]) -> list[list[float]]:
    provider = get_settings().opensearch_embedding_provider
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=get_settings().openai_api_key)
        resp = client.embeddings.create(model=_OPENAI_MODEL, input=texts)
        return [d.embedding for d in resp.data]
    return _local_model().encode(texts, show_progress_bar=False).tolist()


def ensure_index(dims: int | None = None) -> None:
    client = get_client()
    index = get_settings().opensearch_index
    dims = dims or embed_dims()
    if client.indices.exists(index=index):
        return
    client.indices.create(
        index=index,
        body={
            "settings": {"index": {"knn": True}},
            "mappings": {
                "properties": {
                    "kb_id": {"type": "keyword"},
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


def ingest(kb_ids: list[str] | None = None) -> int:
    chunks: list[Chunk] = iter_chunks(kb_ids)
    if not chunks:
        return 0
    ensure_index()
    vectors = embed([c.text for c in chunks])
    index = get_settings().opensearch_index
    actions = [
        {
            "_index": index,
            "_id": c.chunk_id,
            "_source": {
                "kb_id": c.kb_id,
                "doc_name": c.doc_name,
                "heading": c.heading,
                "text": c.text,
                "embedding": vec,
            },
        }
        for c, vec in zip(chunks, vectors)
    ]
    helpers.bulk(get_client(), actions)
    get_client().indices.refresh(index=index)
    return len(actions)


def query(text: str, k: int = 5, kb_ids: list[str] | None = None) -> list[OpenSearchHit]:
    vector = embed([text])[0]
    body: dict = {
        "size": k,
        "query": {
            "knn": {"embedding": {"vector": vector, "k": k}},
        },
    }
    if kb_ids:
        body["query"] = {
            "bool": {
                "must": [{"knn": {"embedding": {"vector": vector, "k": k}}}],
                "filter": [{"terms": {"kb_id": kb_ids}}],
            }
        }
    resp = get_client().search(index=get_settings().opensearch_index, body=body)
    return [
        OpenSearchHit(
            doc_name=hit["_source"]["doc_name"],
            heading=hit["_source"]["heading"],
            text=hit["_source"]["text"],
            score=hit["_score"],
            kb_id=hit["_source"]["kb_id"],
        )
        for hit in resp["hits"]["hits"]
    ]
