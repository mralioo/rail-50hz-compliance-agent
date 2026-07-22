"""Draftsman agent: sketch elements onto the plan from clicked points.

Deliberately NOT a CAD engine: the planner clicks points on the render
canvas, the agent connects them (for now: cable lines), computes real-world
geometry from the render's world window, and returns an overlay element plus
a chat confirmation with rule reminders. The DXF itself is never modified.
"""
import json
import math
import uuid

from app.agent import rag
from app.agent.client import load_prompt
from app.core.config import get_settings
from app.models.schemas import DrawnElement, DrawResponse

MIN_POINTS = 2


class DraftError(ValueError):
    pass


def _parse_instruction(instruction: str) -> tuple[str, str]:
    """(kind, label) — LLM when available, keyword fallback otherwise."""
    settings = get_settings()
    if settings.agent_mode == "openai" and settings.openai_api_key:
        try:
            from openai import OpenAI

            fallback_prompt = (
                'Return JSON {"kind": "cable_line|line|conduit|marker", '
                '"label": "short name"} for the sketch instruction.'
            )
            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model=settings.openai_model,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": load_prompt("draftsman.md", fallback_prompt)},
                    {"role": "user", "content": instruction},
                ],
                max_tokens=60,
            )
            data = json.loads(response.choices[0].message.content)
            return (
                str(data.get("kind") or "cable_line")[:24],
                str(data.get("label") or "Cable line")[:40],
            )
        except Exception:
            pass
    lower = instruction.lower()
    if any(w in lower for w in ("kabel", "cable", "leitung")):
        return "cable_line", "Cable line"
    return "line", "Line"


def _image_to_world(
    point: tuple[float, float], world: tuple[float, float, float, float]
) -> tuple[float, float]:
    x0, y0, x1, y1 = world
    return (x0 + point[0] * (x1 - x0), y0 + (1.0 - point[1]) * (y1 - y0))


def draw(
    instruction: str,
    points_image: list[tuple[float, float]],
    render_meta: dict | None,
) -> DrawResponse:
    if render_meta is None:
        raise DraftError("No render available — the canvas mapping is missing.")
    if len(points_image) < MIN_POINTS:
        raise DraftError(
            "Pick at least two points on the render canvas first "
            "(enable draw mode, then click)."
        )

    world = tuple(render_meta["world"])
    points_world = [_image_to_world(p, world) for p in points_image]
    length = sum(
        math.dist(points_world[i], points_world[i + 1])
        for i in range(len(points_world) - 1)
    )
    bends = max(len(points_world) - 2, 0)
    kind, label = _parse_instruction(instruction)

    notes = [f"{len(points_world)} points, {bends} bend(s), total length {length:.1f} m."]
    if kind == "cable_line":
        rules = rag.load_rules()
        notes.append(
            f"Reminder: keep a bending radius of >= {rules.min_bending_radius_mm:g} mm "
            f"at every bend and pulling force <= {rules.max_pulling_force_n:g} N "
            "(Ril 954.9101 §4.2)."
        )
    note = " ".join(notes)

    element = DrawnElement(
        id=uuid.uuid4().hex[:8],
        kind=kind,
        label=label,
        points_image=points_image,
        points_world=points_world,
        length=round(length, 2),
        note=note,
    )
    reply = (
        f"Drawn: {label} ({kind.replace('_', ' ')}) through {len(points_world)} "
        f"point(s) — {length:.1f} m. {notes[-1] if kind == 'cable_line' else ''} "
        "This is a sketch overlay for planning discussion; the CAD file itself "
        "is not modified."
    ).strip()
    return DrawResponse(element=element, reply=reply)
