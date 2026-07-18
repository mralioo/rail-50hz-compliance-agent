# Rail50Hz.ai — Compliance Agent POC

Automated compliance assistant for 50 Hz auxiliary power planning documents in
DACH railway infrastructure. Converts DWG → DXF, structures the geometry
mathematically (`ezdxf` + `shapely`), and runs an AI agent that validates the
extracted parameters against DB Ril / VDE guidelines — catching template drift
(retired guideline citations) and physical violations (bending radii, pulling
forces) before they reach EBA review.

## Documentation

Full documentation lives in [`docs/`](docs/README.md):
[Architecture & system design](docs/ARCHITECTURE.md) ·
[API reference](docs/API.md) ·
[Backend guide](docs/BACKEND.md) ·
[Frontend guide](docs/FRONTEND.md) ·
[Deployment & ops](docs/DEPLOYMENT.md)

## Architecture

```
[Flutter Planner's Playground]  (Linux/macOS/Windows/web desktop workspace)
          │  HTTP multipart upload + status polling + agent chat
          ▼
[FastAPI Gateway]  backend/app/api          (local dev or GCP Cloud Run)
          ▼
[Pipeline Orchestrator]  backend/app/pipeline
   1. ingestion/   DWG → DXF (ODA File Converter; DXF passes through)
   2. extraction/  ezdxf entity parsing → shapely metrics (areas, lengths,
                   bend radii / pulling forces from annotations)
   3. agent/       compliance analysis
        ├── MockAgentClient    rule-based, credential-free (default)
        └── VertexAgentClient  Vertex AI Gemini + RAG over data/regulations/
          ▼
[ComplianceReport JSON]  → findings + Erläuterungsbericht summary
```

## Repository layout

```
backend/
  app/
    api/          REST routes (upload, job status, agent chat)
    core/         env-driven settings (mock vs. vertex, ODA path, …)
    models/       pydantic schemas — the single API contract
    ingestion/    upload staging + ODA DWG→DXF conversion
    extraction/   DXF parsing (ezdxf) + spatial math (shapely)
    agent/        agent clients, mini-RAG, system prompt
    pipeline/     job store + end-to-end orchestrator
  data/regulations/   mock DB Ril corpus (machine-readable limits + prose)
  scripts/        demo DXF generator with injected violations
  tests/
frontend/         Flutter desktop app (three-panel planner dashboard)
  lib/
    core/         API client, config, theme
    models/       Dart mirrors of the backend schemas
    state/        Riverpod providers (pipeline lifecycle, chat)
    features/     ingestion / canvas / data_view / console panels
deployment/       Dockerfile + Cloud Build → Cloud Run
```

## Quickstart

```bash
# 1. Backend
make setup            # venv + deps
make sample           # generate backend/data/samples/sample_plan.dxf
make backend          # gateway on http://localhost:8000  (docs at /docs)

# 2. Frontend (separate terminal)
cd frontend && flutter pub get
make frontend         # flutter run -d linux

# 3. Demo: drop sample_plan.dxf into the app. The agent flags:
#    - "Ril 954.0107" citation      → template drift (retired guideline)
#    - R=90mm bending radius        → below the 150 mm minimum
#    - 620 N pulling force          → above the 500 N maximum

# 4. Raw DWG: with LibreDWG's dwg2dxf installed (docs/DEPLOYMENT.md §3),
#    drop any .dwg file — e.g. from dataset/test_dwg/ — and the pipeline
#    converts it automatically (verified on AutoCAD 2000–2018 files).
```

Run tests with `make test`.

### API

| Method | Path                     | Description                          |
| :----- | :----------------------- | :----------------------------------- |
| POST   | `/api/v1/jobs`           | Upload `.dwg`/`.dxf`, starts pipeline |
| GET    | `/api/v1/jobs/{id}`      | Job status + data payload + report   |
| POST   | `/api/v1/jobs/{id}/chat` | Ask the agent about the processed plan |
| GET    | `/api/v1/health`         | Liveness                             |

### Configuration

Copy `backend/.env.example` → `backend/.env`. Key switches:

- `AGENT_MODE=mock` (default, no credentials) or `vertex` (Vertex AI Gemini;
  uncomment `google-genai` in `requirements.txt` and set `GCP_PROJECT`).
- DWG conversion — LibreDWG `dwg2dxf` is auto-detected (`PATH` /
  `~/.local/bin` / `DWG2DXF_PATH`); the ODA File Converter
  (`ODA_CONVERTER_PATH`) is an optional fallback. `.dxf` needs neither.
- `LLM_API_KEY` / `OPENAI_API_KEY` — OpenAI key for the Cognee memory layer
  and per-plan summaries (dataset ingestion; see docs/DATASET_INGESTION.md).

Frontend targets a different backend via
`flutter run --dart-define=API_BASE_URL=https://<cloud-run-url>`.

### Deploy (GCP)

```bash
gcloud builds submit --config deployment/cloudbuild.yaml .
```

## Extending

- **Real regulations:** drop more `.md` files into `backend/data/regulations/`
  — the machine-readable limit block + prose sections are picked up
  automatically. Swap `agent/rag.py` for Vertex AI Search embeddings.
- **More CAD entities:** add cases in `extraction/dxf_parser.py`; the
  `Geometry` schema and canvas painter already handle new kinds generically.
- **Persistence/scale-out:** replace the in-memory `JobStore`
  (`pipeline/orchestrator.py`) with Firestore/Redis.
- **Other OS:** the Flutter app is scaffolded for Linux, macOS, Windows and
  web (`flutter run -d <device>`).

> ⚠️ Liability for final validation remains with the human engineer.
