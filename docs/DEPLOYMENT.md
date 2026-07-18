# Deployment & Operations

## 1. Local Development

```bash
# one-time
make setup                 # python venv + backend deps
make sample                # generate backend/data/samples/sample_plan.dxf
cd frontend && flutter pub get && cd ..

# run (two terminals)
make backend               # FastAPI on http://localhost:8000 (docs at /docs)
make frontend              # flutter run -d linux
```

All Make targets: `setup · backend · sample · test · frontend · docker`.

## 2. Configuration (`backend/.env`)

Copy `backend/.env.example` → `backend/.env`. Everything is optional for
mock-mode local dev.

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `AGENT_MODE` | `mock` | `mock` = rule-based, credential-free · `vertex` = Vertex AI Gemini |
| `GCP_PROJECT` | — | required when `AGENT_MODE=vertex` |
| `VERTEX_LOCATION` | `europe-west3` | Vertex AI region |
| `VERTEX_MODEL` | `gemini-2.5-flash` | model id |
| `ODA_CONVERTER_PATH` | — | absolute path to the ODA File Converter binary; **only needed for `.dwg` uploads** — `.dxf` is processed directly |
| `WORK_DIR` | `backend/workdir` | upload/conversion staging (gitignored) |

Settings are loaded once (`core/config.py`, cached); restart the server after
changing `.env`.

## 3. ODA File Converter (DWG support)

`.dxf` files work out of the box. For raw `.dwg`:

1. Download the free **ODA File Converter** for your OS from
   <https://www.opendesign.com/guestfiles/oda_file_converter>
   (Linux: `.deb`/`.rpm`/AppImage).
2. Install and locate the binary, e.g.
   `/usr/bin/ODAFileConverter` or `~/Apps/ODAFileConverter.AppImage` (make it
   executable).
3. Set `ODA_CONVERTER_PATH=/path/to/ODAFileConverter` in `backend/.env`.

The pipeline invokes it headlessly as
`ODAFileConverter <in_dir> <out_dir> ACAD2018 DXF 0 1 <filename>` with a 120 s
timeout. A missing binary fails the job with a clear hint instead of crashing
the server.

> Note: inside the Cloud Run container ODA is **not** installed — the deployed
> POC accepts `.dxf` only. Baking ODA into the image (or a dedicated converter
> service) is a post-POC step; see ARCHITECTURE.md §5.

## 4. Vertex AI Mode

```bash
# 1. dependencies (uncomment in backend/requirements.txt, then)
backend/.venv/bin/pip install google-genai

# 2. credentials (local dev)
gcloud auth application-default login

# 3. config
AGENT_MODE=vertex
GCP_PROJECT=<your-project>
```

On Cloud Run, the service account needs the **Vertex AI User** role; env vars
are set by the deploy step below. The `VertexAgentClient` sends the system
prompt (`app/agent/prompts/instruction.md`) + retrieved regulation excerpts +
the payload JSON and enforces a JSON response parsed into `ComplianceReport`.
If the LLM output fails validation the job lands in `failed` — the mock agent
remains the safe demo default.

## 5. Docker

```bash
make docker      # = docker build -f deployment/Dockerfile -t rail50hz-backend .
docker run --rm -p 8080:8080 rail50hz-backend
# gateway now on http://localhost:8080
```

The image (`python:3.12-slim`) contains `app/` + `data/` (regulation corpus
included), stages uploads under `/tmp/workdir`, and serves via uvicorn on
`$PORT` (Cloud Run convention).

## 6. GCP Cloud Run (via Cloud Build)

```bash
# one-time: Artifact Registry repo
gcloud artifacts repositories create rail50hz \
    --repository-format=docker --location=europe-west3

# build + push + deploy
gcloud builds submit --config deployment/cloudbuild.yaml .
```

`deployment/cloudbuild.yaml` builds the image, pushes it to
`europe-west3-docker.pkg.dev/$PROJECT_ID/rail50hz/backend:$SHORT_SHA` and
deploys service **rail50hz-backend** with
`AGENT_MODE=vertex, GCP_PROJECT=$PROJECT_ID` and `--allow-unauthenticated`
(hackathon setting — put IAP/auth in front for anything real).

Point the desktop app at it:

```bash
flutter run -d linux --dart-define=API_BASE_URL=https://<cloud-run-url>
```

### Operational caveats (POC)

- **Jobs are in-memory** — a new revision/instance forgets old job ids
  (clients get 404 and simply re-upload). Max one instance
  (`--max-instances=1`) keeps polling consistent.
- **No auth / no rate limiting** — hackathon scope.
- CORS is `*` by default (`cors_origins` in `core/config.py`).

## 7. CI Hooks (suggested)

Both suites are fast and dependency-free of GCP/ODA — CI-safe:

```bash
cd backend && .venv/bin/python -m pytest tests/ -q     # 3 tests, <1 s
cd frontend && flutter analyze && flutter test         # zero-issue baseline
```
