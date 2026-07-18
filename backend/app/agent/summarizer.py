"""One-paragraph plan summaries via the OpenAI API.

Used by the dataset ingestion flow to turn a refined DataLayerPayload into a
human-readable engineering summary before it goes into Cognee memory.
Degrades gracefully: returns None when OPENAI_API_KEY is not configured.
"""
from collections import Counter

from app.core.config import get_settings
from app.models.schemas import DataLayerPayload

SYSTEM_PROMPT = (
    "You are an assistant for DACH railway electrical planning engineers. "
    "Given structured data extracted from a CAD plan (layers, geometry metrics, "
    "text annotations), write ONE concise paragraph (max 90 words) describing "
    "what the plan contains: rooms/areas, cable runs, notable electrical "
    "parameters (bending radii, pulling forces), and any guideline citations. "
    "Be factual; do not invent data that is not present."
)


def payload_digest(payload: DataLayerPayload, max_texts: int = 20) -> str:
    """Compact, token-cheap text form of a payload for LLM input."""
    kinds = Counter(g.kind for g in payload.geometries)
    lines = [
        f"file: {payload.source_file}",
        f"layers: {', '.join(payload.layers)}",
        f"entities: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())),
        "metrics: "
        + ("; ".join(
            f"{m.name}={m.value:g}{m.unit} ({m.layer})" for m in payload.metrics[:40]
        ) or "none"),
        "annotations: "
        + (" | ".join(t.text for t in payload.texts[:max_texts] if t.text) or "none"),
    ]
    return "\n".join(lines)


def summarize_payload(payload: DataLayerPayload) -> str | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    from openai import OpenAI  # deferred: optional dependency

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_summary_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": payload_digest(payload)},
        ],
        max_tokens=200,
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip() or None
