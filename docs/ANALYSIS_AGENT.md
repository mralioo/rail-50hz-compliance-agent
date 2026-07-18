# Analysis Agent — Per-Finding Deep Dive on Locator Results

**Use case:** after the locator agent highlights regions ("wo ist der
Betonkabelkanal" → 7 boxes), the planner wants to *triage* them: see a quick
overview of each finding, hide the irrelevant ones, click into one to
investigate, and only then spend an AI call on a detailed description.

Status: ✅ implemented and verified on `Kreuzungsplan.dwg` (2026-07-18).
Builds on [LOCATOR_AGENT.md](LOCATOR_AGENT.md).

## 1. Design principle: two tiers, tokens only on demand

| Tier | Trigger | Cost | Content |
| :--- | :--- | :--- | :--- |
| **Overview** (`analyze`) | automatic, right after locate | pure local math, no LLM | entities in/near the region by kind, layers present, nearby annotations, region size, per-layer metric aggregates (run lengths, areas) |
| **Description** (`describe`) | **only when the planner clicks "Describe (AI)"** | one gpt-4o-mini call (~160 output tokens) | 2–3 plain-text sentences grounded in the overview + compliance findings on the hit's layer; cached per hit — a second click never re-requests |

This is deliberate: a locate can return 12 hits, and describing all of them
unprompted would be 12 wasted LLM calls. The overview is free and usually
enough to decide *where* to look; the AI text is opt-in per finding.

## 2. UI — findings panel (bottom, under the render)

When the locator returns hits, the bottom data panel switches from the
metrics table to the **findings list**:

```
Findings for "wo ist der Betonkabelkanal" — 7 region(s)   [Hide all] [✕]
──────────────────────────────────────────────────────────────────────
👁  Betonkabelkanal Gr. II/III i.F.
    117 entities (24 polyline, 93 line) · 8 layers · 10 annotations   ▼
      Layers: VG-BLO-Einfriedungen, VG-BLO-Fahrbahnmarkierung, …
      Metrics: total run length on layer: 328.6 m; 12 enclosed area(s)…
      Annotations: HET 2b | FS13a | …
      [✨ Describe (AI)]        ← click = one request, then cached
👁̶  Betonkabelkanal Gr. I i.F.   (box hidden on canvas)
    50 entities (13 polyline, 37 line) · 5 layers · 7 annotations
...
```

- **Eye toggle per row** — shows/hides that hit's box on the render canvas
  (amber = visible); *Hide all / Show all* in the header; the canvas chip
  counts `shown/total`.
- **Expand a row** — selects the finding: its box turns **deep orange,
  thicker, drawn on top** so the planner sees instantly which region they're
  investigating. Collapse deselects.
- **Describe (AI)** — spinner while fetching, result rendered as a text card
  in the row. Failures degrade to an inline message; without an OpenAI key
  the backend answers with a deterministic rule-based description instead.
- **✕ / chip delete** — back to the metrics table; a new upload clears
  everything automatically.

## 3. API

### `POST /api/v1/jobs/{id}/hits/analyze`
Body `{"hits": [LocateHit, …]}` → `{"analyses": [HitAnalysis, …]}` (order
preserved). Deterministic; called once per locate with all hits batched.

`HitAnalysis`: `label, layer, bbox_size[w,h], entity_count,
entities_by_kind{}, layers[], annotations[], metrics_summary`.
Region = hit bbox + a 4 %-of-plan context ring.

### `POST /api/v1/jobs/{id}/hits/describe`
Body `{"hit": LocateHit, "analysis": HitAnalysis?}` → `{"description": str}`.
LLM-backed under `AGENT_MODE=openai` (grounded in the overview + compliance
findings whose `location` mentions the hit's layer; output passed through
`ensure_prose()`), deterministic fallback otherwise. Both endpoints: 409
before extraction, 404 for unknown jobs.

## 4. Verified results (live server, Kreuzungsplan.dwg)

- `analyze` on the 7 Betonkabelkanal hits: e.g. hit 1 → *117 entities
  (24 polyline, 93 line), 8 layers, 10 annotations, total run length on layer
  328.6 m, 12 enclosed areas* — all computed locally in one request.
- `describe` on hit 1 (one click): *"The Betonkabelkanal Gr. II/III i.F. is a
  concrete cable channel designed to accommodate and protect electrical
  cables within the railway infrastructure. It is surrounded by … road
  markings (VG-BLO-Fahrbahnmarkierung) and fencing (VG-BLO-Einfriedungen) …
  There are no compliance issues identified on this layer …"*

## 5. Files

| File | Change |
| :--- | :--- |
| `backend/app/agent/analyzer.py` | new — `analyze_hit()` (deterministic), `describe_hit()` (LLM + fallback) |
| `backend/app/models/schemas.py` | `HitAnalysis`, analyze/describe request/response models; `LocateHit.layer` |
| `backend/app/api/routes.py` | `/hits/analyze`, `/hits/describe`, shared `_processed_job()` guard |
| `frontend/lib/models/locate.dart` | `HitAnalysis` model, `LocateHit.toJson()` round-trip |
| `frontend/lib/state/locate_provider.dart` | session state: per-hit visibility, selection, cached analysis/description |
| `frontend/lib/features/data_view/findings_panel.dart` | new — the findings list UI |
| `frontend/lib/features/data_view/data_table_panel.dart` | switches metrics ⇄ findings |
| `frontend/lib/features/canvas/plan_viewer.dart` | visible-only boxes, selected hit emphasized (deep orange, on top) |

## 6. Limitations & next steps

- Region membership is point-in-bbox — a long line crossing the region with
  both endpoints outside is missed; segment-bbox intersection would fix it.
- Clicking a box on the canvas doesn't select the row yet (selection flows
  panel → canvas only); hit-testing taps through the InteractiveViewer
  transform is the natural follow-up.
- "Zoom to finding" on selection would complete the investigation loop.
- Same INSERT/ATTRIB blind spot as the locator: block-internal content is
  invisible to the overview counts until the parser traverses blocks.
