"""Locator agent: visual grounding of planner queries on the plan.

Given "where is the Betonschalthaus?", it resolves the query to search terms
(LLM-assisted when AGENT_MODE=openai, keyword fallback otherwise), matches
them against extracted annotations and layer names, and returns bounding
boxes in world coordinates plus normalized positions on the render image —
which the frontend draws as highlight overlays on the canvas.
"""
import json
import re

from app.core.config import get_settings
from app.models.schemas import DataLayerPayload, LocateHit, LocateResponse

STOPWORDS = {
    # en
    "where", "is", "are", "the", "a", "an", "in", "on", "of", "show", "me",
    "find", "locate", "please", "can", "you", "point", "to", "at", "plan",
    "canvas", "render", "highlight", "region", "component",
    # de
    "wo", "ist", "sind", "der", "die", "das", "ein", "eine", "im", "am",
    "auf", "zeig", "zeige", "mir", "bitte", "finde", "markiere", "bereich",
}

MAX_HITS = 12
TEXT_PAD_FRACTION = 0.02  # bbox padding around a text anchor, of plan extent

# Chat-friendly color words (en + de) an engineer can say alongside a locate
# query ("highlight the 50 Hz Schrank in red" / "markiere ... rot") -> hex,
# resolved by _resolve_color and stamped onto every LocateHit this call
# returns. Deliberately small and literal (no color-theory fuzzing) so the
# mapping stays predictable to read back in the UI.
NAMED_COLORS = {
    "red": "#e03131", "rot": "#e03131",
    "orange": "#f08c00",
    "yellow": "#f2c200", "gelb": "#f2c200",
    "green": "#2f9e44", "grün": "#2f9e44", "gruen": "#2f9e44",
    "blue": "#1971c2", "blau": "#1971c2",
    "cyan": "#0c8599", "türkis": "#0c8599", "tuerkis": "#0c8599",
    "teal": "#0c8599", "turquoise": "#0c8599",
    "purple": "#9c36b5", "violet": "#9c36b5", "lila": "#9c36b5",
    "magenta": "#c2255c", "pink": "#e64980", "rosa": "#e64980",
    "white": "#f1f3f5", "weiss": "#f1f3f5", "weiß": "#f1f3f5",
    "black": "#1a1a1a", "schwarz": "#1a1a1a",
    "gray": "#868e96", "grey": "#868e96", "grau": "#868e96",
    "amber": "#f08c00", "lime": "#66a80f", "navy": "#1864ab",
}

_HEX_RE = re.compile(r"^#?[0-9a-fA-F]{6}$|^#?[0-9a-fA-F]{3}$")


def _resolve_color(raw: str | None) -> str | None:
    """Normalizes a chat-supplied color word or hex code to "#rrggbb", ready
    for annotate.py's per-hit true_color DXF attribute. Unrecognized input is
    dropped (None) rather than raising - a bad/misheard color word shouldn't
    fail the locate itself, just fall back to the default highlight color."""
    if not raw:
        return None
    raw = raw.strip().lower()
    if raw in NAMED_COLORS:
        return NAMED_COLORS[raw]
    if _HEX_RE.match(raw):
        hexval = raw if raw.startswith("#") else f"#{raw}"
        if len(hexval) == 4:  # #rgb -> #rrggbb
            hexval = "#" + "".join(c * 2 for c in hexval[1:])
        return hexval
    return None


def _naive_terms(query: str) -> list[str]:
    words = re.findall(r"[\wäöüß-]{3,}", query.lower())
    return [w for w in words if w not in STOPWORDS]


def _llm_terms(query: str) -> list[str] | None:
    settings = get_settings()
    if settings.agent_mode != "openai" or not settings.openai_api_key:
        return None
    try:
        from openai import OpenAI

        from app.agent.client import load_prompt

        fallback = (
            "Extract the CAD component/region the user wants to find on a "
            'German railway plan. Return JSON {"terms": [...]}: the mentioned '
            "component names plus German synonyms/word stems likely used in "
            "CAD layer names or annotations. Lowercase, max 6."
        )
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": load_prompt("locator.md", fallback)},
                {"role": "user", "content": query},
            ],
        )
        terms = json.loads(response.choices[0].message.content).get("terms", [])
        return [str(t).lower() for t in terms][:6] or None
    except Exception:
        return None  # never fail a locate because term expansion failed


def _tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[-_+\s./]+", name.lower()) if len(t) >= 3]


def _match_score(term: str, candidate: str) -> float:
    """1.0 exact, 0.8 substring either way (compound words), else 0."""
    if term == candidate:
        return 1.0
    if term in candidate or candidate in term:
        return 0.8
    return 0.0


def _world_to_image(
    bbox: tuple[float, float, float, float], meta: dict
) -> tuple[float, float, float, float] | None:
    x0, y0, x1, y1 = meta["world"]
    if x1 == x0 or y1 == y0:
        return None
    nx0 = (bbox[0] - x0) / (x1 - x0)
    nx1 = (bbox[2] - x0) / (x1 - x0)
    # image y is down, world y is up
    ny0 = 1.0 - (bbox[3] - y0) / (y1 - y0)
    ny1 = 1.0 - (bbox[1] - y0) / (y1 - y0)
    clamp = lambda v: min(max(v, 0.0), 1.0)
    return (clamp(nx0), clamp(ny0), clamp(nx1), clamp(ny1))


def locate(
    payload: DataLayerPayload,
    query: str,
    render_meta: dict | None,
    color: str | None = None,
) -> LocateResponse:
    resolved_color = _resolve_color(color)
    # Strip the color word itself out of term extraction only - "highlight
    # the Kabeltrog in red" shouldn't let "red"/"rot" compete as a search
    # term against layer/annotation text (the original `query` still comes
    # back on the response untouched).
    search_query = re.sub(re.escape(color), "", query, flags=re.IGNORECASE) if color else query
    terms = _llm_terms(search_query) or _naive_terms(search_query)
    hits: list[LocateHit] = []

    if payload.bounds and terms:
        min_x, min_y, max_x, max_y = payload.bounds
        pad = max(max_x - min_x, max_y - min_y) * TEXT_PAD_FRACTION

        # 1) annotation text matches → point anchors with padded boxes
        for item in payload.texts:
            candidates = _tokens(item.text) + [item.text.lower().strip()]
            score = max(
                (_match_score(t, c) for t in terms for c in candidates),
                default=0.0,
            )
            if score > 0:
                x, y = item.position
                hits.append(
                    LocateHit(
                        label=item.text.strip()[:60],
                        source="text",
                        confidence=score,
                        layer=item.layer,
                        anchor=(x, y),
                        world_bbox=(x - pad, y - pad, x + pad, y + pad),
                    )
                )

        # 2) layer-name matches → bbox over that layer's geometry
        for layer in payload.layers:
            score = max(
                (_match_score(t, c) for t in terms for c in _tokens(layer)),
                default=0.0,
            )
            if score == 0:
                continue
            points = [p for g in payload.geometries if g.layer == layer for p in g.points]
            if not points:
                continue
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            hits.append(
                LocateHit(
                    label=f"Layer: {layer}",
                    source="layer",
                    confidence=score * 0.9,  # coarser than a text anchor
                    layer=layer,
                    anchor=((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2),
                    world_bbox=(min(xs), min(ys), max(xs), max(ys)),
                )
            )

    hits.sort(key=lambda h: h.confidence, reverse=True)
    hits = hits[:MAX_HITS]

    if resolved_color:
        for hit in hits:
            hit.color = resolved_color

    render_size = None
    if render_meta:
        render_size = tuple(render_meta["px"])
        for hit in hits:
            hit.image_bbox = _world_to_image(hit.world_bbox, render_meta)

    return LocateResponse(query=query, terms=terms, hits=hits, render_size=render_size)
