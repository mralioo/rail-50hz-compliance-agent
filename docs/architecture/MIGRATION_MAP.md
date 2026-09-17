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
| 11 | documents (extraction) | *(new — no old module; ported from `reference_codebase/`, the ITUKI backend's design)* | `app/domain/documents/`, `app/adapters/documents/`, `app/pipelines/` (generic engine), `app/application/documents/`, `app/application/shared_steps/` | **done** |

Row 11 is not a migration of existing code — see `docs/DOCUMENT_EXTRACTION.md` for the
full design, and the note below on why the generic pipeline *engine* (row 11) landed at
`app/pipelines/` directly rather than waiting for row 9 (`jobs`), which is about migrating
the old compliance-analysis orchestrator (`app/pipeline/`, singular) to a *per-context*
pipeline under the same `app/pipelines/` root — both rows share one engine, they don't
conflict.

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
- **Row 11 naming reconciliation (2026-08-21)**: the `documents` slice was first built
  copying `reference_codebase/`'s exact ITUKI folder names (`app/infrastructure/...`,
  `app/domain/pipeline/...`). That directly contradicts this file's own decision above
  (`adapters/` over ITUKI's `infrastructure/`) and MIGRATION_MAP row 2's already-stated
  target (`app/adapters/ingestion/`). Reconciled by renaming to this repo's convention:
  `app/infrastructure/*` → `app/adapters/documents/*` (flattened to one file per tech,
  matching `app/adapters/cad/`); `app/domain/data/documents/{models,ports}/*` →
  `app/domain/documents/{models.py,ports.py}` (flattened to one file per concern,
  matching `app/domain/cad/ports.py` — dropped the extra ITUKI `data/` nesting level,
  since no other context here groups contexts under a `data/` parent); `app/domain/
  pipeline/*` → `app/pipelines/*` (top-level, matching `docs/system_design/System
  Design.pdf`'s explicit `/pipelines/*` path and `reference_codebase/backend/pipelines/`
  itself, which is *also* top-level, not nested under `domain/` — so this specific ITUKI
  path was actually consistent with this repo's design all along; the first pass got it
  wrong by nesting it, not by copying ITUKI). IoC wiring added to `app/bootstrap.py`
  (`get_document_conversion_client`, `get_document_text_extraction_client`,
  `get_document_file_storage`), matching the `cad` slice's composition-root pattern.
  Going forward: `reference_codebase/` is a useful reference for *behavior* (what a
  slice should do, e.g. the Docling adapter's crop math) but its folder *names* are not
  authoritative for this repo — always translate `infrastructure/` → `adapters/` and
  keep bounded-context folders one level deep, per the decision above.

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
