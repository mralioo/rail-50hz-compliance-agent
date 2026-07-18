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
│   │   └── converter.py      ensure_dxf(): DWG→DXF via ODA, DXF passthrough
│   ├── extraction/
│   │   ├── dxf_parser.py     parse_dxf(): entities → Geometry/TextItem
│   │   └── geometry.py       compute_metrics() + compute_bounds()
│   ├── agent/
│   │   ├── client.py         AgentClient ABC, Mock + Vertex implementations
│   │   ├── rag.py            load_rules() + retrieve() over data/regulations/
│   │   └── prompts/instruction.md   LLM system prompt (JSON output schema)
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

1. **`converting`** — `ensure_dxf()`. `.dxf` returns unchanged; `.dwg`
   shells out to the ODA File Converter
   (`ODAFileConverter <in_dir> <out_dir> ACAD2018 DXF 0 1 <file>`).
   Missing `ODA_CONVERTER_PATH` raises a `ConversionError` with a hint.
2. **`extracting`** — `parse_dxf()` + `compute_metrics()` + `compute_bounds()`
   assemble the `DataLayerPayload`.
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

- `load_rules()` parses these `key: value` lines (last file wins per key)
- `retrieve(query)` does keyword scoring over `## `-delimited prose sections
  and returns the top-k excerpts for LLM grounding / chat replies

**Adding a regulation = dropping a new `.md` file.** No code changes.
To add a new *rule type*: add the key to `RuleSet` in `rag.py` and a check in
`MockAgentClient.analyze()`.

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
