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

### 1.1 Test a new (raw) DWG file end-to-end

DWG upload works out of the box once `dwg2dxf` is installed (see §3 — on this
machine it already is, at `~/.local/bin/dwg2dxf`, and the backend auto-detects
it there; no `.env` entry needed).

```bash
# terminal 1 — backend
make backend                     # http://localhost:8000

# terminal 2 — frontend
make frontend                    # Flutter desktop app
```

Then in the app: **drop any `.dwg` file** (e.g. one from `dataset/test_dwg/`)
onto the drop zone — or click it and browse. Watch the status bar walk
through *Uploading → Converting (DWG → DXF) → Extracting Geometry →
AI Compliance Analysis → Ready*; the canvas then renders the plan geometry,
the bottom table fills with metrics, and the agent console answers questions
about it.

Without the frontend, the same test via curl:

```bash
curl -F "file=@dataset/test_dwg/e1gkwpmo.dwg" localhost:8000/api/v1/jobs
# → {"id": "<job_id>", "status": "queued", ...}
curl localhost:8000/api/v1/jobs/<job_id>      # poll until "status": "ready"
```

> Expectation for real-world plans: geometry renders, but many production DWGs
> keep text inside block references (`INSERT`/`ATTRIB`), which the extractor
> does not traverse yet — so annotations/citation findings may be empty for
> now (see DATASET_INGESTION.md §5.2). The demo file
> `backend/data/samples/sample_plan.dxf` always shows the full compliance
> flow with 3 violations.

## 2. Configuration (`backend/.env`)

Copy `backend/.env.example` → `backend/.env`. Everything is optional for
mock-mode local dev.

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `AGENT_MODE` | `mock` | `mock` = rule-based, credential-free · `openai` = OpenAI API (needs `OPENAI_API_KEY`) · `vertex` = Vertex AI Gemini |
| `OPENAI_MODEL` | `gpt-4o-mini` | model for the OpenAI compliance agent |
| `GCP_PROJECT` | — | required when `AGENT_MODE=vertex` |
| `VERTEX_LOCATION` | `europe-west3` | Vertex AI region |
| `VERTEX_MODEL` | `gemini-2.5-flash` | model id |
| `DWG2DXF_PATH` | auto-detected | LibreDWG `dwg2dxf` binary for `.dwg` uploads; found automatically on `PATH` or in `~/.local/bin` — set only for a custom location |
| `ODA_CONVERTER_PATH` | — | ODA File Converter binary (optional alternative engine; used when `dwg2dxf` is absent) |
| `WORK_DIR` | `backend/workdir` | upload/conversion staging (gitignored) |
| `LLM_API_KEY` | — | OpenAI key **for Cognee memory** (dataset ingestion / memory chat) |
| `OPENAI_API_KEY` | — | OpenAI key for the per-plan summarizer (set to the same key) |
| `OPENAI_SUMMARY_MODEL` | `gpt-4o-mini` | model used for one-paragraph plan summaries |

Settings are loaded once (`core/config.py`, cached); restart the server after
changing `.env`.

## 3. DWG Support (DWG → DXF engines)

`.dxf` files work with no converter at all. For raw `.dwg`, the backend picks
the first available engine in this order:

### Engine A — LibreDWG `dwg2dxf` (default, open source) ✅ installed here

Built from the 0.14 source release (no Linux binaries are published and it is
not in Ubuntu's apt). Reproduce on any Linux machine with gcc/make:

```bash
curl -sLO https://github.com/LibreDWG/libredwg/releases/download/0.14/libredwg-0.14.tar.xz
tar xf libredwg-0.14.tar.xz && cd libredwg-0.14
./configure --disable-bindings --disable-shared --prefix="$HOME/.local"
make -j"$(nproc)" && make install        # → ~/.local/bin/dwg2dxf  (~2 min)
```

Auto-detection order: `DWG2DXF_PATH` env var → `dwg2dxf` on `PATH` →
`~/.local/bin/dwg2dxf`. Invoked as `dwg2dxf -y -o <out.dxf> <in.dwg>` with a
120 s timeout; non-zero exit with a valid output file is tolerated (LibreDWG
warns on recoverable issues).

**Verified against the project dataset:** all six DWG generations present in
`dataset/test_dwg/` (AutoCAD 2000/AC1015 → 2018/AC1032) convert and then parse
cleanly through the ezdxf extraction pipeline — details in
DATASET_INGESTION.md §5.

### Engine B — ODA File Converter (optional, higher fidelity)

1. Download from <https://www.opendesign.com/guestfiles/oda_file_converter>
   (manual license acceptance required).
2. Set `ODA_CONVERTER_PATH=/path/to/ODAFileConverter` in `backend/.env`.

Invoked headlessly as `ODAFileConverter <in_dir> <out_dir> ACAD2018 DXF 0 1
<filename>`. Used only when `dwg2dxf` is not found.

With neither engine installed, a `.dwg` job fails with a clear hint (the
server keeps running and `.dxf` uploads still work).

> Note: the Cloud Run image contains **neither** engine yet — the deployed POC
> accepts `.dxf` only. Compiling LibreDWG into the Docker image is a
> straightforward post-POC step (multi-stage build); see ARCHITECTURE.md §5.

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
