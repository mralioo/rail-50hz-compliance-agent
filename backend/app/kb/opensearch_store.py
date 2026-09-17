"""OpenSearch-backed semantic (vector) retrieval over the regulation corpus.

Evaluation-harness backend, parallel to `app.agent.rag`'s keyword search —
not wired into `routes.py`/`/chat`. See docs/OPENSEARCH_NEO4J_EVALUATION.md.

Three embedding providers, picked via OPENSEARCH_EMBEDDING_PROVIDER:
- "local" (default): `sentence-transformers` — free, offline, needs no
  network, pulls in torch.
- "openai": OpenAI's `text-embedding-3-small` (reuses OPENAI_API_KEY).
- "vllm": the remote embedding model already used for Docling extraction and
  by the org's own indexing_service (`intfloat/multilingual-e5-large`, over
  the network at VLLM_EMBEDDINGS_BASE_URL) — no local model weights or API
  key needed, at the cost of a network round trip per embed() call. Chosen
  when the goal is "index locally, but don't run/download an embedding model
  ourselves" — see docs/OPENSEARCH_NEO4J_EVALUATION.md §9.
"""
import logging
from dataclasses import dataclass
from functools import lru_cache

import httpx
from opensearchpy import OpenSearch, helpers

from app.core.config import get_settings
from app.kb.corpus import Chunk, iter_chunks

logger = logging.getLogger(__name__)

_LOCAL_MODEL_NAME = "all-MiniLM-L6-v2"
_LOCAL_DIMS = 384
_OPENAI_MODEL = "text-embedding-3-small"
_OPENAI_DIMS = 1536
_VLLM_DIMS = 1024  # intfloat/multilingual-e5-large


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
    if provider == "openai":
        return _OPENAI_DIMS
    if provider == "vllm":
        return _VLLM_DIMS
    return _LOCAL_DIMS


_VLLM_MAX_CHARS = 1500  # e5-large's context window is ~512 tokens; some chunk
# sources (e.g. app.kb.project_corpus's heading-only split, on a document with
# no real Docling heading markup) can produce a single chunk spanning an
# entire multi-page document. Truncate defensively client-side (~375
# chars/token estimate, conservative margin) rather than let the server
# reject an oversized input - a documented, visible quality tradeoff instead
# of a hard failure.
_VLLM_MIN_CHARS = 50  # floor for the halving retry below
_VLLM_MAX_RETRIES = 5


def _embed_one_vllm(client: httpx.Client, url: str, model: str, text: str) -> list[float]:
    """Embed a single (already prefixed) text, halving its length on a 400 —
    this server's max-context error is a *combined* budget: observed a batch
    of 32 short chunks (815 tokens total) rejected with "maximum context
    length is 512 tokens", even though every individual item was well under
    that alone. Sending one item per request sidesteps the summed-batch
    budget; halving handles the rarer case where a single (already truncated
    to _VLLM_MAX_CHARS) chunk is still, alone, over the per-item limit -
    dense technical German/English text can tokenize more richly than the
    conservative chars-per-token estimate assumes.
    """
    for attempt in range(_VLLM_MAX_RETRIES):
        response = client.post(url, json={"model": model, "input": [text]})
        if response.status_code == 200:
            return response.json()["data"][0]["embedding"]
        if response.status_code == 400 and len(text) > _VLLM_MIN_CHARS:
            text = text[: max(_VLLM_MIN_CHARS, len(text) // 2)]
            logger.warning(
                "_embed_vllm: item still over context limit, retrying at %d chars (attempt %d)",
                len(text),
                attempt + 1,
            )
            continue
        response.raise_for_status()
    raise RuntimeError(
        f"_embed_vllm: gave up after {_VLLM_MAX_RETRIES} halving attempts, "
        f"final length {len(text)} chars"
    )


def _embed_vllm(texts: list[str], is_query: bool) -> list[list[float]]:
    """E5 models are trained with a "query: "/"passage: " instruction prefix —
    skipping it measurably hurts retrieval quality, so this isn't optional.

    One HTTP request per text (not batched) - see _embed_one_vllm's docstring
    for why: this server enforces its 512-token context limit as a *combined*
    budget across every item in a single request, not per item.
    """
    settings = get_settings()
    prefix = "query: " if is_query else "passage: "
    url = f"{settings.vllm_embeddings_base_url.rstrip('/')}/v1/embeddings"
    timeout = httpx.Timeout(connect=30.0, read=60.0, write=30.0, pool=30.0)

    truncated = sum(1 for t in texts if len(t) > _VLLM_MAX_CHARS)
    if truncated:
        logger.warning(
            "_embed_vllm: truncated %d/%d oversized chunk(s) to %d chars before embedding",
            truncated,
            len(texts),
            _VLLM_MAX_CHARS,
        )

    embeddings: list[list[float]] = []
    with httpx.Client(timeout=timeout) as client:
        for t in texts:
            safe = t[:_VLLM_MAX_CHARS] if len(t) > _VLLM_MAX_CHARS else t
            embeddings.append(_embed_one_vllm(client, url, settings.embedding_model, prefix + safe))
    return embeddings


def embed(texts: list[str], is_query: bool = False) -> list[list[float]]:
    provider = get_settings().opensearch_embedding_provider
    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=get_settings().openai_api_key)
        resp = client.embeddings.create(model=_OPENAI_MODEL, input=texts)
        return [d.embedding for d in resp.data]
    if provider == "vllm":
        return _embed_vllm(texts, is_query)
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
    vector = embed([text], is_query=True)[0]
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
