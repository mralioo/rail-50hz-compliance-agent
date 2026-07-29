# Rail50Hz.ai — Compliance Agent POC

Automated compliance assistant for 50 Hz auxiliary power planning documents in
DACH railway infrastructure. Reads real DWG/DXF plans, structures the geometry
mathematically (`ezdxf` + `shapely`), and runs an AI agent that validates the
extracted parameters against DB Ril / VDE guidelines — catching template drift
(retired guideline citations) and physical violations (bending radii, pulling
forces) before they reach EBA review. Ships with two front ends: a Flutter
desktop app and a zero-install browser console with an interactive 3D CAD
viewer.

## Documentation

Full documentation lives in [`docs/`](docs/README.md) — start there for the
complete index. Highlights:
[Architecture & system design](docs/ARCHITECTURE.md) ·
[API reference](docs/API.md) ·
[Backend guide](docs/BACKEND.md) ·
[Frontend guide](docs/FRONTEND.md) ·
[CAD engine framework](docs/CAD_ENGINE_FRAMEWORK.md) ·
[cad-viewer / Engineer's Console](docs/CAD_VIEWER_INTEGRATION.md) ·
[Deployment & ops](docs/DEPLOYMENT.md)

## Components

| Component | What it does | Lives in |
| :--- | :--- | :--- |
| **FastAPI gateway** | REST surface: upload, job status/polling, chat, locate, draftsman sketch, DWG read/manipulate, viewer/console | `backend/app/api/routes.py` |
| **Pipeline orchestrator** | Background job: convert → extract → compute metrics → agent analysis, in-memory `JobStore` | `backend/app/pipeline/` |
| **Ingestion + extraction** | DWG→DXF conversion, robust DXF parsing (`ezdxf.recover`), geometry/metric math (`shapely`) | `backend/app/ingestion/`, `backend/app/extraction/` |
| **Compliance agent** | Rule-based (`mock`), OpenAI, or Vertex AI Gemini client; grounded in the regulation corpus + optional Cognee memory | `backend/app/agent/` |
| **CAD engine framework** | One `CadEngine` interface behind which ezdxf, LibreDWG, ACadSharp (.NET), and QCAD all read/write DXF/DWG — powers the raw `/jobs/{id}/dwg` read+edit+download API | `backend/app/cad_engines/`, `backend/tools/` |
| **Interactive browser viewer** | Wraps the open-source `mlightcad/cad-viewer` (Three.js/WebGL) into a self-contained, pannable/zoomable HTML export of any plan — no Flutter required | `backend/app/viewer/` |
| **Engineer's Console** | Browser sidebar around that viewer: chat, locate-and-highlight, findings triage, search history, draftsman click-to-sketch, knowledge-base selector, and a drag-and-drop upload landing page | `backend/app/viewer/assets/console_shell.html`, `console_upload.html` |
| **Flutter Planner's Playground** | Desktop/web three-panel app: canvas + data table + chat console, same backend API | `frontend/lib/` |

## Dependencies

**Required** (everything else is optional and gracefully degrades / is
feature-gated):

- Python 3.12 + the packages in `backend/requirements.txt` (`fastapi`,
  `ezdxf`, `shapely`, `pydantic`, …) — `make setup` installs these into
  `backend/.venv`.

**Optional, each unlocking one feature** (auto-detected on `PATH` / common
install locations, or pointed at explicitly via `backend/.env` — see
`backend/.env.example` for every variable):

| Dependency | Unlocks | Env var(s) |
| :--- | :--- | :--- |
| LibreDWG `dwg2dxf`/`dxf2dwg` | Reading/writing real `.dwg` files (preferred engine) | `DWG2DXF_PATH`, `DXF2DWG_PATH` |
| ODA File Converter | Higher-fidelity DWG↔DXF alternative | `ODA_CONVERTER_PATH` |
| .NET 8 SDK + `tools/acadsharp_cli` | ACadSharp engine — the only engine that round-trips DWG reliably for the `/dwg/manipulate` API | `DOTNET_PATH`, `ACADSHARP_CLI_PATH` |
| Qt6/CMake + built `qcadcmd` | QCAD engine (DXF-only; unbuilt/unverified in this environment) | `QCADCMD_PATH` |
| Node.js 20+ + `tools/cad_viewer_cli` (npm install + Playwright Chromium) | The interactive browser viewer / Engineer's Console | `NODE_PATH`, `CAD_VIEWER_CLI_PATH` |
| `OPENAI_API_KEY` | `AGENT_MODE=openai` compliance agent + chat, dataset summaries, Cognee memory | `OPENAI_API_KEY`, `LLM_API_KEY` |
| GCP project + `google-genai` | `AGENT_MODE=vertex` compliance agent | `GCP_PROJECT`, `VERTEX_LOCATION` |
| Flutter SDK | The desktop/web frontend | — |

Without any optional dependency, the backend still runs end-to-end against
`.dxf` uploads with `AGENT_MODE=mock` (no credentials needed).

## Run commands

```bash
# 1. Backend
make setup             # venv + Python deps
make sample             # generate backend/data/samples/sample_plan.dxf
make backend             # gateway on http://localhost:8000  (docs at /docs)

# 2a. Browser console (no Flutter needed) — separate terminal
make viewer                          # opens an upload page: drop any real .dwg/.dxf
make viewer FILE=path/to/plan.dwg    # or upload a specific file directly
#   checks deps (node, the cad-viewer exporter CLI, Playwright Chromium),
#   starts the backend if it isn't already running, opens the browser.
#   See docs/CAD_VIEWER_INTEGRATION.md for one-time setup
#   (cd backend/tools/cad_viewer_cli && npm install && npx playwright install chromium).

# 2b. Flutter app instead/as well — separate terminal
cd frontend && flutter pub get
make frontend         # flutter run -d linux

# 3. Demo: drop sample_plan.dxf into either front end. The agent flags:
#    - "Ril 954.0107" citation      → template drift (retired guideline)
#    - R=90mm bending radius        → below the 150 mm minimum
#    - 620 N pulling force          → above the 500 N maximum

# 4. Raw DWG: with LibreDWG's dwg2dxf installed (docs/DEPLOYMENT.md §3),
#    upload any .dwg file — e.g. from dataset/test_dwg/ — and the pipeline
#    converts it automatically (verified on AutoCAD 2000–2018 files, and on
#    real DB Netz plans with large survey coordinates — see
#    docs/CAD_VIEWER_INTEGRATION.md §10 for a rendering-precision bug found
#    and fixed against that exact case).
```

Run tests with `make test`.

## Architecture

```
[Flutter Planner's Playground]   OR   [Browser: Engineer's Console]
  (desktop/web three-panel app)         (chat/findings/history/sketch/KB
          │                              sidebar + interactive cad-viewer)
          │  HTTP multipart upload + status polling + agent chat
          ▼
[FastAPI Gateway]  backend/app/api          (local dev or GCP Cloud Run)
          ▼
[Pipeline Orchestrator]  backend/app/pipeline
   1. ingestion/   DWG → DXF (LibreDWG / ODA File Converter; DXF passes through)
   2. extraction/  ezdxf entity parsing → shapely metrics (areas, lengths,
                    bend radii / pulling forces from annotations)
   3. agent/       compliance analysis
        ├── MockAgentClient    rule-based, credential-free (default)
        ├── OpenAIAgentClient  gpt-4o-mini, knowledge-base-scoped chat
        └── VertexAgentClient  Vertex AI Gemini + RAG over data/regulations/
          ▼
[ComplianceReport JSON]  → findings + Erläuterungsbericht summary

Separately, on demand:
[cad_engines framework] → raw DWG/DXF read + structured edits + real .dwg
                            write-back (independent of the extraction pipeline)
[app/viewer]             → interactive HTML export (mlightcad/cad-viewer),
                            with locator hits / draftsman sketches baked in
                            as real, selectable geometry
```

## Repository layout

```
backend/
  app/
    api/          REST routes (upload, job status, chat, locate, draw, dwg, viewer)
    core/         env-driven settings (agent mode, engine paths, …)
    models/       pydantic schemas — the single API contract
    ingestion/    upload staging, DWG→DXF conversion, DXF→DWG write-back
    extraction/   DXF parsing (ezdxf) + spatial math (shapely) + PNG renderer
    agent/        agent clients, locator/analyzer/draftsman agents, mini-RAG
    cad_engines/  engine-agnostic DWG/DXF read/write framework (ezdxf/
                   LibreDWG/ACadSharp/QCAD behind one CadEngine interface)
    viewer/       interactive cad-viewer export + Engineer's Console (HTML/JS)
    memory/       search history (SQLite) + Cognee guideline memory bridge
    pipeline/     job store + end-to-end orchestrator
  tools/          acadsharp_cli (.NET), cad_viewer_cli (Node), qcad_connector (JS)
  data/regulations/   mock DB Ril corpus (machine-readable limits + prose),
                        organized as selectable knowledge-base folders
  data/samples/   demo DXF/DWG fixtures, incl. a real DB Netz crossing plan
  scripts/        demo DXF generator, engine benchmarks, browser-launch script
  tests/
frontend/         Flutter desktop/web app (three-panel planner dashboard)
  lib/
    core/         API client, config, theme
    models/       Dart mirrors of the backend schemas
    state/        Riverpod providers (pipeline lifecycle, chat)
    features/     ingestion / canvas / data_view / console panels
deployment/       Dockerfile + Cloud Build → Cloud Run
```

### API

Full reference with request/response examples: [docs/API.md](docs/API.md).
Most-used endpoints:

| Method | Path                     | Description                          |
| :----- | :----------------------- | :----------------------------------- |
| POST   | `/api/v1/jobs`           | Upload `.dwg`/`.dxf`, starts pipeline |
| GET    | `/api/v1/jobs`           | Recent jobs (lightweight listing)    |
| GET    | `/api/v1/jobs/{id}`      | Job status + data payload + report   |
| POST   | `/api/v1/jobs/{id}/chat` | Ask the agent about the processed plan (optionally knowledge-base-scoped) |
| GET    | `/api/v1/console`        | Browser upload landing page (no job id needed) |
| GET    | `/api/v1/jobs/{id}/console` | Engineer's Console — chat/findings/history/sketch sidebar + interactive viewer |
| GET    | `/api/v1/jobs/{id}/viewer` | Bare interactive cad-viewer HTML export |
| GET    | `/api/v1/jobs/{id}/dwg`  | Raw DWG/DXF read via the CAD engine framework |
| POST   | `/api/v1/jobs/{id}/dwg/manipulate` | Apply structured edits, write a new `.dwg` |
| GET    | `/api/v1/knowledge-bases` | List selectable regulation-corpus knowledge bases |
| GET    | `/api/v1/health`         | Liveness                             |

### Configuration

Copy `backend/.env.example` → `backend/.env`. Key switches (see the
Dependencies table above for what each optional one unlocks):

- `AGENT_MODE=mock` (default, no credentials), `openai`, or `vertex`.
- DWG conversion — LibreDWG `dwg2dxf`/`dxf2dwg` auto-detected (`PATH` /
  `~/.local/bin`); ODA File Converter is an optional fallback. `.dxf` needs
  neither.
- ACadSharp/QCAD/cad-viewer paths (`DOTNET_PATH`, `ACADSHARP_CLI_PATH`,
  `QCADCMD_PATH`, `NODE_PATH`, `CAD_VIEWER_CLI_PATH`) — all auto-detected on
  `PATH`/common locations, override only if needed.
- `LLM_API_KEY` / `OPENAI_API_KEY` — OpenAI key for the `openai` agent mode,
  Cognee memory layer, and per-plan summaries.

Frontend targets a different backend via
`flutter run --dart-define=API_BASE_URL=https://<cloud-run-url>`.

### Deploy (GCP)

```bash
gcloud builds submit --config deployment/cloudbuild.yaml .
```

## Extending

- **Real regulations:** drop more `.md` files into `backend/data/regulations/`
  (or a subfolder to create a new selectable knowledge base) — picked up
  automatically, no code changes. Swap `agent/rag.py` for Vertex AI Search
  embeddings for real semantic retrieval.
- **More CAD entities:** add cases in `extraction/dxf_parser.py`; the
  `Geometry` schema and canvas painter already handle new kinds generically.
- **More CAD engines / DWG fidelity:** implement `CadEngine`
  (`cad_engines/base.py`) and register it in `cad_engines/registry.py`.
- **Persistence/scale-out:** replace the in-memory `JobStore`
  (`pipeline/orchestrator.py`) with Firestore/Redis.
- **Other OS:** the Flutter app is scaffolded for Linux, macOS, Windows and
  web (`flutter run -d <device>`); the browser console works anywhere a
  modern browser does, no build step.

> ⚠️ Liability for final validation remains with the human engineer.
