# Backend architecture

The backend (`backend/app/`) is migrating from a flat, hackathon-POC layout to
**Domain-Driven Design + Hexagonal Architecture (Ports & Adapters) + Inversion of Control +
Pipes & Filters** — see `docs/architecture/SYSTEM_DESIGN.md` for the pattern itself, and
`docs/architecture/MIGRATION_MAP.md` for what's migrated so far.

Scope: **backend only**. The UI (`webapp/`, `frontend/`) is untouched — every `/api/v1/...`
route keeps its existing request/response shape (`app/models/schemas.py`) throughout the
migration, so the UI never has to change.

## Why

This backend already juggles several genuinely interchangeable services per concern: four CAD
engines (ezdxf / ACadSharp / LibreDWG / QCAD), three compliance-agent backends (mock / OpenAI /
Vertex), and two knowledge stores being evaluated side by side (OpenSearch / Neo4j) — plus a
DWG→DXF converter that already picks between two binaries. "Modular and interchangeable with
different services" isn't aspirational here, it's already the shape of the problem. The goal of
this restructure is to make that swappability a first-class pattern everywhere instead of an
`if/elif` in one function (`app/agent/client.py::get_agent()` today) or a hand-rolled dict
registry (the old `app/cad_engines/registry.py`).

## Layers

```
Deployment (backend/app/api/)
   -> Application Services (backend/app/application/services/)
   -> Pipeline Engine (backend/app/pipelines/)
   -> Core Domain (backend/app/domain/) — models, domain services, Ports
   -> Adapters (backend/app/adapters/) — implement ports using real tech
   -> Infrastructure — the actual external systems (FreeCAD, OpenSearch, LLM APIs, ...)
```

The rule that makes this work: **`app/domain/` never imports `app/adapters/`.** A port
(`app/domain/<context>/ports.py`) is a `Protocol`/`ABC` the domain defines; an adapter
(`app/adapters/<context>/<tech>_adapter.py`) implements it. The only place that imports a
concrete adapter class and decides which one to use is `app/bootstrap.py` — the IoC
composition root, equivalent to ITUKI's `backend/src/backend/bootstrap.py`.

## Bounded contexts

One subfolder per bounded context under each of `domain/`, `adapters/`, `pipelines/` — same
organizational style as `/home/alioo/Desktop/ITUC_repo/ITUKI_python` (its
`domain/tendering` + `infrastructure/tendering` + `application/tendering` split), applied to
this repo's actual features rather than that repo's. See `MIGRATION_MAP.md` for the full list
and status; `cad` is migrated and is the reference example to copy for the rest:

- `app/domain/cad/ports.py` — `CadEnginePort`, `ParsedDrawing`, `EngineError`
- `app/domain/cad/services.py` — `apply_edits` (pure domain logic on a `ParsedDrawing`)
- `app/adapters/cad/{ezdxf,acadsharp,libredwg,qcad}_adapter.py` — one class per engine
- `app/bootstrap.py::get_cad_engine(name)` — IoC: `?engine=` query param -> adapter instance

## How to add a new adapter (e.g. a 5th CAD engine, or a new LLM provider)

1. Implement the domain's `Protocol`/`ABC` for that context in a new
   `app/adapters/<context>/<tech>_adapter.py`. No changes to `app/domain/` — that's the point.
2. Register it in `app/bootstrap.py`'s dict/factory for that context.
3. Nothing else changes: pipelines, application services, and API routes only ever reference
   the port type, never the concrete adapter, so they don't know or care that a new one exists.

## Tooling note

Unlike ITUKI_python, this repo keeps **pip + venv + `requirements.txt`**, not a `uv` workspace —
a deliberate choice (see `docs/architecture/MIGRATION_MAP.md`'s decision log) to avoid adding
packaging-tool risk on top of the several fragile native toolchains this backend already
depends on (FreeCAD, ODA, LibreDWG, .NET/ACadSharp, Node, xpra). Only the module layout and
layering style are adopted from ITUKI, not its tooling.
