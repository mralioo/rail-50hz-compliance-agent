# UX & Memory Update — Six Features (2026-07-18)

All verified live on `Kreuzungsplan.dwg` / `sample_plan.dxf`.

## 1. New search resets the findings list ✅
The findings `ListView` and row tiles are keyed on the query
(`findings-<query>`), so a new locator search discards scroll position,
expanded rows and selection from the previous result set.

## 2. Search history (database) ✅
Every locate query is saved to SQLite (`WORK_DIR/history.db`,
`app/memory/history.py`) with timestamp, job, filename and hit count.
- API: `GET /api/v1/searches?limit=20`.
- UI: history icon in the Plan Copilot header → bottom sheet of past
  searches; tapping one re-runs it against the current plan.

## 3. Cognee guideline memory connected ✅
- `app/memory/cognee_store.py` — selective bridge: `recall(query, k=2)`
  returns ≤2 snippets of ≤400 chars; disabled/unseeded/timeout ⇒ `[]` and
  agents fall back to the local `rag.py` corpus. Gated by
  `COGNEE_ENABLED=true` + `LLM_API_KEY`.
- Seeding: `python scripts/seed_memory.py` ingests `data/regulations/*.md`
  (+ optional `data/norms/`). **Drop more guideline/norm files there and
  re-run to refine agent answers.**
- Consumers: chat agent and per-finding describer inject "Guideline memory"
  into their prompts. Verified: chat cites the 150 mm rule recalled from
  memory. ⚠️ Recall is LLM-routed → adds ~15–25 s to a memory-backed chat
  turn (timeout 30 s); snippet caching is the obvious next optimization.
- **Per-agent system prompts** now live as editable files in
  `app/agent/prompts/`, each carrying the project context (Rail50Hz.ai,
  DACH 50 Hz, DB Energie, Ril/VDE): `instruction.md` (compliance analyst),
  `chat.md` (Plan Copilot), `locator.md` (term expansion), `describe.md`
  (component describer). Code falls back to built-in prompts if a file is
  missing.

## 4. Chat: selectable text, editable queries, renamed agent ✅
- The console is now the **Plan Copilot** (it converses with the DWG —
  compliance Q&A, component search, explanations — not only compliance).
- The whole message list sits in a `SelectionArea` → any text can be
  selected/copied.
- Tapping one of your own earlier messages loads it back into the input for
  editing & resending (query manipulation).
- New macro chip "Where is the Schalthaus?" showcases the locator.

## 5. UI/UX pass ✅
- **Quick guide** dialog (❓ in the app bar): 4-step walkthrough (upload →
  canvas → copilot → findings).
- Drop zone hints: demo file path + supported AutoCAD versions.
- Tooltips on Render/Vectors toggle, layer filter, history, visibility eyes.
- Input helper text advertising the "wo ist …" pattern.

## 6. Layer filter on the canvas ✅
- Layers popup (badge shows hidden count) next to the view toggle;
  per-layer checkboxes + "Show all".
- **Vector view:** filtered client-side in the painter.
- **Render view:** `GET /jobs/{id}/render?layers=a,b` re-renders only those
  layers server-side (ezdxf layer visibility), cached per layer-set hash,
  and **pinned to the base render's world window** so locator overlays stay
  aligned. Verified: 2-layer variant = 12.7 KB vs 648 KB full render.

## 7. Browser console (Engineer's Console) — see CAD_VIEWER_INTEGRATION.md §9
All of the above (search history, layer filter, chat, Cognee-grounded
replies) plus locate-highlight, findings, and draftsman sketching now also
exist as a browser-based sidebar around the interactive cad-viewer export
(`GET /jobs/{id}/console`, opened by `make viewer`) — a separate surface
from the Flutter app described in this doc. Full design, endpoint list, and
verified results: [CAD_VIEWER_INTEGRATION.md](CAD_VIEWER_INTEGRATION.md) §9.

## Files touched
Backend: `memory/cognee_store.py`, `memory/history.py`,
`scripts/seed_memory.py`, `agent/prompts/{chat,locator,describe}.md`,
`agent/client.py`, `agent/analyzer.py`, `agent/locator.py`,
`extraction/renderer.py` (layers/world params), `api/routes.py`
(`/searches`, render `?layers=`, history save), `core/config.py`,
`.env.example`.
Frontend: `agent_console.dart` (rewrite), `plan_viewer.dart` (layer filter),
`plan_canvas.dart` (hiddenLayers), `findings_panel.dart` (reset keys),
`api_client.dart` (history), `chat_provider.dart`, `app.dart` (guide),
`file_drop_zone.dart`.
