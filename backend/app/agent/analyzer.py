"""Analysis agent: per-hit deep dive on locator results.

Two tiers, deliberately split to conserve tokens:
- `analyze_hit()` — deterministic region overview (entities, layers, nearby
  annotations, metric aggregates). Pure local math, safe to run for every hit.
- `describe_hit()` — short AI-written description grounded in that overview
  plus the compliance report. Called only when the planner explicitly clicks
  "Describe" in the UI; falls back to a rule-based sentence without OpenAI.
"""
from collections import Counter

from app.agent.client import ensure_prose, load_prompt
from app.core.config import get_settings
from app.memory import cognee_store
from app.models.schemas import (
    ComplianceReport,
    DataLayerPayload,
    HitAnalysis,
    LocateHit,
)

CONTEXT_PAD_FRACTION = 0.04  # extra context ring around the hit bbox
MAX_ANNOTATIONS = 12


def _inside(p: tuple[float, float], bbox: tuple[float, float, float, float]) -> bool:
    return bbox[0] <= p[0] <= bbox[2] and bbox[1] <= p[1] <= bbox[3]


def _context_bbox(
    bbox: tuple[float, float, float, float],
    bounds: tuple[float, float, float, float] | None,
) -> tuple[float, float, float, float]:
    if not bounds:
        return bbox
    pad = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) * CONTEXT_PAD_FRACTION
    return (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)


def analyze_hit(payload: DataLayerPayload, hit: LocateHit) -> HitAnalysis:
    ctx = _context_bbox(hit.world_bbox, payload.bounds)

    region_geos = [
        g for g in payload.geometries if any(_inside(p, ctx) for p in g.points)
    ]
    kinds = Counter(g.kind for g in region_geos)
    layers = sorted({g.layer for g in region_geos})
    annotations = [
        t.text.strip() for t in payload.texts if t.text.strip() and _inside(t.position, ctx)
    ][:MAX_ANNOTATIONS]

    parts: list[str] = []
    if hit.layer:
        layer_metrics = [m for m in payload.metrics if m.layer == hit.layer]
        run_total = sum(m.value for m in layer_metrics if m.name == "run_length")
        areas = [m.value for m in layer_metrics if m.name == "room_area"]
        if run_total:
            parts.append(f"total run length on layer: {run_total:.1f} m")
        if areas:
            parts.append(f"{len(areas)} enclosed area(s), largest {max(areas):.1f} m²")
    if not parts:
        parts.append("no aggregated metrics on this layer")

    return HitAnalysis(
        label=hit.label,
        layer=hit.layer,
        bbox_size=(
            hit.world_bbox[2] - hit.world_bbox[0],
            hit.world_bbox[3] - hit.world_bbox[1],
        ),
        entity_count=len(region_geos),
        entities_by_kind=dict(kinds),
        layers=layers,
        annotations=annotations,
        metrics_summary="; ".join(parts),
    )


def _related_findings(report: ComplianceReport | None, hit: LocateHit) -> list[str]:
    if report is None or not hit.layer:
        return []
    return [
        f"[{f.status.value}] {f.parameter}: {f.actual} (expected {f.expected})"
        for f in report.findings
        if f.location and hit.layer in f.location
    ]


def describe_hit(
    payload: DataLayerPayload,
    report: ComplianceReport | None,
    hit: LocateHit,
    analysis: HitAnalysis | None,
) -> str:
    analysis = analysis or analyze_hit(payload, hit)
    findings = _related_findings(report, hit)
    settings = get_settings()

    if settings.agent_mode == "openai" and settings.openai_api_key:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=settings.openai_api_key)
            memory = cognee_store.recall(hit.label)
            context = (
                f"Component: {hit.label} (source: {hit.source}, layer: {hit.layer})\n"
                f"Region size: {analysis.bbox_size[0]:.1f} x {analysis.bbox_size[1]:.1f} "
                f"drawing units\n"
                f"Entities: {analysis.entity_count} ({analysis.entities_by_kind})\n"
                f"Layers present: {', '.join(analysis.layers) or 'none'}\n"
                f"Annotations in region: {' | '.join(analysis.annotations) or 'none'}\n"
                f"Metrics: {analysis.metrics_summary}\n"
                f"Compliance findings on this layer: {'; '.join(findings) or 'none'}\n"
                f"Guideline memory: {' | '.join(memory) or 'none'}"
            )
            fallback = (
                "You are a railway electrical planning assistant. In 2-3 "
                "plain-text sentences (no markdown, no JSON), describe what "
                "this located plan component is, what surrounds it, and any "
                "compliance relevance. Only use the provided data; German "
                "technical terms may stay German."
            )
            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": load_prompt("describe.md", fallback)},
                    {"role": "user", "content": context},
                ],
                max_tokens=160,
            )
            reply = ensure_prose(response.choices[0].message.content or "")
            if reply:
                return reply
        except Exception:
            pass  # fall through to the deterministic description

    sentences = [
        f"{hit.label}: region of {analysis.entity_count} entities "
        f"({', '.join(f'{v} {k}' for k, v in analysis.entities_by_kind.items()) or 'no geometry'}) "
        f"across {len(analysis.layers)} layer(s)."
    ]
    if analysis.annotations:
        sentences.append(f"Nearby annotations: {' | '.join(analysis.annotations[:4])}.")
    sentences.append(
        f"Compliance: {findings[0]}." if findings else "No compliance findings on this layer."
    )
    return " ".join(sentences)
