# Backend Guide

Python 3.12 · FastAPI · ezdxf · shapely. Lives in `backend/`; the importable
package is `backend/app/`.

## Module Map

```
backend/
├── app/
│   ├── main.py               FastAPI factory (CORS, router mount)
│   ├── core/config.py        Settings — env vars / .env, cached singleton
│   ├── models/schemas.py     Pydantic contract (see docs/API.md)
│   ├── api/routes.py         /api/v1 endpoints
│   ├── ingestion/
│   │   ├── storage.py        save_upload(): stages files under workdir/<job_id>/
│   │   └── converter.py      ensure_dxf(): dual-engine DWG→DXF (LibreDWG dwg2dxf / ODA), DXF passthrough
│   ├── extraction/
│   │   ├── dxf_parser.py     parse_dxf(): entities → Geometry/TextItem
│   │   ├── geometry.py       compute_metrics() + compute_bounds()
│   │   └── renderer.py       render_png(): ezdxf drawing add-on → PNG (incl. blocks)
│   ├── agent/
│   │   ├── client.py         AgentClient ABC, Mock/OpenAI/Vertex + chat guards
│   │   ├── locator.py        visual grounding: query → plan regions
│   │   ├── analyzer.py       per-hit overview (local) + AI description (on click)
│   │   ├── summarizer.py     one-paragraph plan summaries (OpenAI)
│   │   ├── rag.py            load_rules() + retrieve() over data/regulations/
│   │   └── prompts/          per-agent system prompts: instruction.md (analyst),
│   │                         chat.md (Plan Copilot), locator.md, describe.md
│   ├── memory/
│   │   ├── cognee_store.py   selective guideline recall (COGNEE_ENABLED)
│   │   └── history.py        locator search history (SQLite in WORK_DIR)
│   └── pipeline/orchestrator.py     JobStore + run_pipeline()
├── data/
│   ├── regulations/          mock DB Ril corpus (see format below)
│   └── samples/sample_plan.dxf      generated demo plan
├── scripts/make_sample_dxf.py
└── tests/test_extraction.py
```

## Pipeline Stages (`pipeline/orchestrator.py`)

`run_pipeline(job, source_path)` runs as a FastAPI background task and updates
the shared `job_store` after every stage, so polling clients see progress:

1. **`converting`** — `ensure_dxf()`. `.dxf` returns unchanged; `.dwg` is
   converted by the first available engine: LibreDWG **`dwg2dxf`**
   (auto-detected via `DWG2DXF_PATH` → `PATH` → `~/.local/bin`; invoked as
   `dwg2dxf -y -o out.dxf in.dwg`), falling back to the **ODA File Converter**
   when `ODA_CONVERTER_PATH` is set. Neither installed → `ConversionError`
   with a setup hint. Build/verification notes: DEPLOYMENT.md §3,
   DATASET_INGESTION.md §5.
2. **`extracting`** — a best-effort `render_png()` writes
   `workdir/<job_id>/render.png` (served by `GET /jobs/{id}/render`; render
   failures never fail the job), then `parse_dxf()` + `compute_metrics()` +
   `compute_bounds()` assemble the `DataLayerPayload`.
3. **`analyzing`** — `get_agent().analyze(payload)` returns the
   `ComplianceReport`.
4. **`ready`** — payload + report available. Any exception at any stage sets
   `failed` + `Job.error`.

`JobStore` is an in-memory dict behind a lock. It is intentionally the only
stateful thing in the backend — replace it (plus `storage.py`) to scale out.

## Extraction Rules (`extraction/`)

Supported DXF entities (`dxf_parser.py`, modelspace only):

| DXF type | Mapped to | Notes |
| :--- | :--- | :--- |
| `LWPOLYLINE` | `Geometry(kind="polyline")` | preserves `closed` flag |
| `LINE` | `Geometry(kind="line")` | two points |
| `CIRCLE` | `Geometry(kind="circle")` | center point + `radius` |
| `TEXT` / `MTEXT` | `TextItem` | `TEXT` reads `entity.dxf.text`; `MTEXT` uses `plain_text()` |

To support more entities (ARC, HATCH, INSERT…): add a case in `parse_dxf()`.
The `Geometry` schema and the Flutter canvas painter handle new `kind`s
generically as long as they reduce to points (+ optional radius).

Metric derivation (`geometry.py`):

- Closed polyline (≥ 3 pts) → `room_area` via `shapely.Polygon.area`
- Open polyline / line (≥ 2 pts) → `run_length` via `shapely.LineString.length`
- Text matching `R\s*=?\s*(\d+)\s*mm` → `cable_bending_radius`
- Text matching `(\d+)\s*N` **and** containing "pull" → `cable_pulling_force`

Units are conventions of the drawing (drawing units = meters for lengths/areas,
annotations carry mm/N explicitly). Adjust the regexes there if your plans
annotate differently.

## Agent (`agent/`)

`get_agent()` picks the implementation from `AGENT_MODE`:

### `MockAgentClient` (default)
Deterministic rule engine against `rag.load_rules()`:
- `cable_bending_radius` ≥ `min_cable_bending_radius_mm`
- `cable_pulling_force` ≤ `max_cable_pulling_force_n`
- any `TextItem` containing a deprecated code → template-drift finding with
  the exact layer + coordinates

`chat()` echoes the current findings and appends the best-matching regulation
excerpt from `rag.retrieve()`.

### `OpenAIAgentClient` (`AGENT_MODE=openai`)
- Requires `OPENAI_API_KEY`; model via `OPENAI_MODEL` (default `gpt-4o-mini`)
- Same prompt strategy as Vertex: `prompts/instruction.md` as system prompt +
  retrieved regulation sections + CAD data, with
  `response_format=json_object` validated into `ComplianceReport`
- `chat()` grounds replies in the report, plan metrics and regulation excerpts

### LLM prompt hygiene (both LLM clients)

- **`payload_digest()`** — real plans produce payloads far too large for a
  prompt (Kreuzungsplan: 243 KB JSON ≈ 62k tokens), so `analyze()` sends a
  compact digest: per-layer aggregated metrics + every annotation with
  coordinates. The mock agent still receives the full typed payload.
- **Missing data ≠ violation** — `instruction.md` mandates `warning` with
  `actual="not specified in plan"` for absent parameters; `non_compliant` is
  reserved for values that conflict with a regulation.
- **`CHAT_SYSTEM_PROMPT` + `ensure_prose()`** — chat uses a conversational
  prompt (the JSON-output contract applies to `analyze()` only), and every
  reply is sanitized server-side (JSON flattened, markdown stripped) so the
  Flutter chat bubble always gets plain text.

### `VertexAgentClient` (`AGENT_MODE=vertex`)
- Requires `GCP_PROJECT` (+ ADC credentials) and `google-genai`
  (uncomment in `requirements.txt`)
- Builds a prompt from `prompts/instruction.md` + retrieved regulation
  sections + the payload JSON; requests `application/json` response and
  validates it straight into `ComplianceReport`

Both implement the same `AgentClient` ABC — new backends (Claude API, local
model) only need `analyze()` and `chat()`.

## Regulation Corpus Format (`data/regulations/*.md`)

Each markdown file may contain a fenced machine-readable block:

```
min_cable_bending_radius_mm: 150
max_cable_pulling_force_n: 500
active_codes: Ril 954.9101, VDE 0100-520
deprecated_codes: Ril 954.0107, Ril 813.0202
```

- `load_rules()` parses these `key: value` lines (last file wins per key) —
  always reads the **full** corpus; ingest-time analysis is not user-filterable
- `retrieve(query, kb_ids=None)` does keyword scoring over `## `-delimited
  prose sections and returns the top-k excerpts for LLM grounding / chat
  replies

**Adding a regulation = dropping a new `.md` file.** No code changes.
To add a new *rule type*: add the key to `RuleSet` in `rag.py` and a check in
`MockAgentClient.analyze()`.

### Knowledge bases (`kb_ids`)

Each immediate subdirectory of `data/regulations/` is its own named,
independently selectable "knowledge base" (e.g. the pre-existing empty
`DB/` → id `db`); loose top-level `*.md` files form the `general` KB.
`list_knowledge_bases()` walks the filesystem live (not cached) — dropping a
file into a KB directory takes effect on the next request, no restart
needed. `retrieve(query, kb_ids=[...])` restricts retrieval to the given
KBs; `kb_ids=None` means the union of **all** KBs — this is a deliberate
widening of the pre-2026-07-29 behavior, which silently ignored
subdirectories (`_read_corpus()` only globbed the top level). Byte-identical
today since `DB/` is empty, but worth knowing: content dropped into a KB
subdirectory is now picked up by any unfiltered `retrieve()` call, not just
by an explicit `kb_ids=["db", ...]` one.

The Engineer's Console (see `CAD_VIEWER_INTEGRATION.md` §9) is the only
caller that ever passes an explicit `kb_ids` today, via
`ChatRequest.knowledge_bases` → `POST /jobs/{id}/chat`. Everything else
(`analyze()`, the mock agent's deprecated-code check, etc.) stays
unfiltered/global by design.

## Testing

```bash
make test        # or: cd backend && .venv/bin/python -m pytest tests/ -v
```

`tests/test_extraction.py` builds a synthetic DXF in `tmp_path` (no ODA, no
GCP, no network) and asserts: entity extraction, metric math (area 50 m²,
length 11 m), and that the mock agent flags the injected 90 mm radius and the
retired Ril citation.

The demo file with three injected violations is regenerated any time with
`make sample` (`scripts/make_sample_dxf.py`).
