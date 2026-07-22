# Draftsman Agent — Sketch Elements on the Render Canvas

**Use case:** the planner clicks points on the render canvas and tells the
Plan Copilot *"draw the cable line NYY-J 5x16 between my points"* — the
agent connects them into a cable-line sketch overlay with real-world length
and rule reminders.

**Scope decision (per user):** no CAD engine, no accurate drafting — the
sketch is a discussion overlay in render-image coordinates. **The DXF/DWG
file is never modified.** Verified live on `Kreuzungsplan.dwg` (2026-07-18).

## 1. Flow

```mermaid
sequenceDiagram
    actor Planner
    participant Canvas as Plan viewer
    participant Chat as Plan Copilot
    participant API as FastAPI
    participant D as Draftsman agent

    Planner->>Canvas: toggle draw mode (pencil icon)
    Planner->>Canvas: click points (numbered cyan markers; undo/clear)
    Planner->>Chat: "draw the cable line NYY-J between my points"
    Chat->>Chat: draw-intent regex (draw|zeichne|verbinde|connect|sketch)
    Chat->>API: POST /jobs/{id}/draw {instruction, points_image}
    API->>D: draw()
    D->>D: LLM parses instruction -> kind/label (fallback: keywords)
    D->>D: image -> world coords (render meta), length, bend count
    D->>D: cable rules reminder (rag.load_rules: 150 mm / 500 N)
    D-->>Chat: DrawnElement + confirmation reply
    Chat->>Canvas: element drawn (cyan polyline + label + length)
```

Fewer than 2 points → the copilot answers with instructions instead of
calling the API. Points are consumed into the element; upload of a new plan
resets everything.

## 2. API

### `GET /api/v1/jobs/{id}/render/meta`
`{world: [x0,y0,x1,y1], px: [w,h]}` — the render's coordinate mapping
(used by the canvas for aspect-true overlays and tap capture).

### `POST /api/v1/jobs/{id}/draw`
Body: `{"instruction": "...", "points_image": [[nx,ny], ...]}` (normalized,
y-down). 422 with a helpful message when <2 points or no render exists.

```json
{
  "element": {
    "id": "1a2b3c4d", "kind": "cable_line", "label": "NYY-J 5x16",
    "points_image": [[0.3,0.5], ...], "points_world": [[3570556.9, ...], ...],
    "length": 59.65,
    "note": "4 points, 2 bend(s), total length 59.6 m. Reminder: keep a bending radius of >= 150 mm ..."
  },
  "reply": "Drawn: NYY-J 5x16 (cable line) through 4 point(s) — 59.6 m. ..."
}
```

Verified: LLM extracted the label "NYY-J 5x16" from the instruction
(prompt file `app/agent/prompts/draftsman.md`, keyword fallback without a
key); length 59.65 m computed in world units via the render's world window;
cable sketches automatically carry the Ril 954.9101 §4.2 reminders
(150 mm bending radius, 500 N pulling force from `rag.load_rules()`).

## 3. UI

- **Pencil icon** (canvas toolbar) toggles draw mode; badge counts picked
  points; **undo / clear** buttons appear alongside. Disabled until the
  render meta is loaded.
- Clicks land as numbered cyan markers — accurate at any zoom because the
  tap layer lives inside the `InteractiveViewer` child (same normalized
  space as all overlays).
- Drawn elements render as cyan polylines with a `label · length m` tag.
- Draw intent in chat routes before locate intent; sketches and points are
  reset on new uploads.

## 4. Files

| File | Change |
| :--- | :--- |
| `backend/app/agent/draftsman.py` | new — instruction parsing, image→world mapping, geometry + rules |
| `backend/app/agent/prompts/draftsman.md` | new — system prompt (project context) |
| `backend/app/models/schemas.py` | `DrawRequest/DrawnElement/DrawResponse` |
| `backend/app/api/routes.py` | `POST /jobs/{id}/draw`, `GET /jobs/{id}/render/meta` |
| `frontend/lib/models/draft.dart`, `state/draft_provider.dart` | new — sketch state |
| `frontend/lib/features/canvas/plan_viewer.dart` | draw mode, tap capture, `_DraftOverlayPainter` |
| `frontend/lib/state/chat_provider.dart` | draw-intent routing |

## 5. Limitations & next steps

- Sketches are session-only overlays (not persisted server-side, not in the
  DXF). Next: persist per job, export as a DXF layer via `ezdxf` write-back —
  the natural bridge from sketch to real CAD edit.
- Straight segments only; no snapping to existing geometry (snap-to-nearest
  cable/wall endpoint would be the first drafting upgrade).
- Compliance check on the sketch is a reminder, not a geometric validation
  (bend radii of the clicked polyline are not measured).
