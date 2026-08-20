# Backend migration map

Tracks the slice-by-slice migration of `backend/app/` to the domain/adapters/pipelines/
application/api pattern described in `docs/architecture/README.md`. Each row is one
self-contained slice: migrate the context end-to-end, update every call site, delete the old
module, verify the app still boots and behaves the same, then move to the next row. This lets
any session (this one or a future one) pick up exactly where the last one left off.

Each slice follows the pattern proven in row 1 (`cad`):
1. `app/domain/<context>/ports.py` — Protocol/ABC port(s) + any pure domain models/errors.
2. `app/domain/<context>/services.py` — pure business logic that doesn't need a port (if any).
3. `app/adapters/<context>/<tech>_adapter.py` — one file per concrete implementation, moved
   as-is from its old location (no logic changes — behavior-preserving refactor).
4. `app/bootstrap.py` — add the context's IoC wiring (which adapter backs the port, chosen
   from `Settings`).
5. Update every import site outside the old module, delete the old module.
6. Verify: `pytest`, `make backend` + `/api/v1/health`, and the specific route(s) that
   exercise this context.

## Status

| # | Context | Old location | New location | Status |
|---|---|---|---|---|
| 1 | cad | `app/cad_engines/` | `app/domain/cad/`, `app/adapters/cad/`, `app/bootstrap.py` | **done** |
| 2 | ingestion | `app/ingestion/` | `app/domain/ingestion/`, `app/adapters/ingestion/` | pending |
| 3 | extraction | `app/extraction/` | `app/domain/extraction/` (pure domain service, likely no port — nothing swaps it today) | pending |
| 4 | compliance | `app/agent/` | `app/domain/compliance/`, `app/adapters/compliance/` | pending |
| 5 | knowledge | `app/kb/` | `app/domain/knowledge/`, `app/adapters/knowledge/` | pending |
| 6 | craftsman | `app/craftsman/` | `app/domain/craftsman/`, `app/adapters/craftsman/` | pending |
| 7 | memory | `app/memory/` | `app/domain/memory/`, `app/adapters/memory/` | pending |
| 8 | viewer | `app/viewer/` | `app/domain/viewer/`, `app/adapters/viewer/` | pending |
| 9 | jobs | `app/pipeline/` | `app/pipelines/document_processing/`, `app/adapters/jobs/` (in-memory `JobRepositoryPort`), `app/application/services/` | pending |
| 10 | api | `app/api/routes.py`, `app/main.py` | `app/api/routes/<context>.py`, `app/api/main.py`, `app/api/deps.py` | pending — do last, once every context routes.py imports has moved |

## Decision log

- **Path naming**: follows `docs/system_design/System Design.pdf`'s explicit paths
  (`domain/`, `domain/<ctx>/ports.py`, `adapters/<ctx>/...`, `pipelines/<ctx>/...`,
  `application/services/...`, `api/...`) rather than ITUKI's folder name for the same layer
  (`infrastructure/`) — the design doc is the primary source of truth the restructure was
  requested against. ITUKI's *organizational style* (one subfolder per bounded context, a
  `bootstrap.py` composition root) is reused regardless of the folder name.
- **Tooling**: kept pip + venv + `requirements.txt`, did not migrate to ITUKI's `uv` workspace
  — this repo already depends on several fragile native toolchains (FreeCAD, ODA, LibreDWG,
  .NET/ACadSharp, Node, xpra); swapping the package manager was judged orthogonal risk not
  worth taking alongside the architecture migration.
- **Pacing**: migrated one bounded context per session/slice rather than big-bang, so a broken
  slice (especially context 6, craftsman/FreeCAD/xpra — the most fragile integration) is caught
  and fixed in isolation instead of compounding with the rest.
- **Scope**: backend only. UI (`webapp/`, `frontend/`) untouched; wire format
  (`app/models/schemas.py`, all `/api/v1/...` paths) unchanged throughout.

## Slice 1 notes (cad) — done

- `CadEngine` ABC → `CadEnginePort` (same class shape: capability flags + `can_read`/
  `can_write`/`read`/`write`; no behavior change).
- `cad_engines/registry.py`'s `ENGINES` dict / `get_engine()` → `bootstrap.py`'s
  `CAD_ENGINES` / `get_cad_engine()` — same lookup, new home (the IoC composition root).
- `cad_engines/manipulate.py` (`apply_edits`/`EditError`) → `domain/cad/services.py` — it's
  pure logic over the domain's `ParsedDrawing`, not an adapter, so it belongs in the domain
  layer, not `adapters/`.
- Call sites updated: `app/api/routes.py` (imports + both `get_engine(...)` call sites),
  `app/craftsman/freecad_bridge.py` (`ParsedDrawing` import + docstring path),
  `app/viewer/annotate.py` (docstring), `app/models/schemas.py` (comments),
  `scripts/engine_bench.py` (imports). `scripts/cad_engine_poc.py` needed no change (doesn't
  import the old module).
