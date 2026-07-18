# API Reference

Base URL: `http://localhost:8000` (local) or your Cloud Run URL.
Interactive OpenAPI docs are served at **`/docs`** while the gateway runs.

All schemas are defined in `backend/app/models/schemas.py` and mirrored in
`frontend/lib/models/job.dart` — **keep both in sync when changing the contract.**

## Endpoints

### `GET /api/v1/health`

Liveness probe. Also reports the **active agent mode** — settings are cached at
server start, so this is the quickest way to spot a server that predates an
`.env` change.

```json
{ "status": "ok", "agent_mode": "openai" }
```

---

### `POST /api/v1/jobs`

Upload a CAD file and start the pipeline. The pipeline runs as a background
task; the response returns immediately with `status: queued`.

- **Body:** `multipart/form-data` with one field `file` (`.dwg` or `.dxf`)
- **400** if the extension is neither `.dwg` nor `.dxf`

```bash
curl -F "file=@backend/data/samples/sample_plan.dxf" \
     http://localhost:8000/api/v1/jobs
```

```json
{
  "id": "0c91e588c5b4",
  "status": "queued",
  "filename": "sample_plan.dxf",
  "error": null,
  "payload": null,
  "report": null
}
```

---

### `GET /api/v1/jobs/{job_id}`

Poll job state. `payload` appears once extraction finishes, `report` once the
agent finishes. **404** if the job id is unknown (also after a server restart —
jobs are in-memory).

Status progression: `queued → converting → extracting → analyzing → ready`
(or `failed` with `error` set).

Response when `ready` (abbreviated):

```json
{
  "id": "0c91e588c5b4",
  "status": "ready",
  "filename": "sample_plan.dxf",
  "error": null,
  "payload": {
    "source_file": "sample_plan.dxf",
    "layers": ["0", "Defpoints", "E_CABINET", "E_CABLE", "E_NOTES", "E_ROOM"],
    "geometries": [
      { "layer": "E_ROOM", "kind": "polyline",
        "points": [[0,0],[12,0],[12,8],[0,8]], "closed": true, "radius": null },
      { "layer": "E_CABLE", "kind": "circle",
        "points": [[11,2]], "closed": false, "radius": 0.15 }
    ],
    "texts": [
      { "layer": "E_NOTES", "text": "acc. to Ril 954.0107", "position": [0.5, 0.3] }
    ],
    "metrics": [
      { "name": "room_area", "value": 96.0, "unit": "m²", "layer": "E_ROOM" },
      { "name": "run_length", "value": 12.3, "unit": "m", "layer": "E_CABLE" },
      { "name": "cable_bending_radius", "value": 90.0, "unit": "mm", "layer": "E_NOTES" },
      { "name": "cable_pulling_force", "value": 620.0, "unit": "N", "layer": "E_NOTES" }
    ],
    "bounds": [0.0, 0.0, 12.0, 8.0]
  },
  "report": {
    "findings": [
      {
        "status": "non_compliant",
        "parameter": "Cable bending radius",
        "actual": "90 mm",
        "expected": ">= 150 mm",
        "regulation": "Ril 954.9101 §4.2",
        "location": "E_NOTES",
        "suggestion": "Re-route the cable run with a wider bend."
      },
      {
        "status": "non_compliant",
        "parameter": "Guideline citation (template drift)",
        "actual": "Ril 954.0107",
        "expected": "Ril 954.9101 / VDE 0100-520",
        "regulation": "Ril 954.9101 §4.5",
        "location": "E_NOTES @ (0.5, 0.3)",
        "suggestion": "Replace citation of retired Ril 954.0107 with the active guideline."
      }
    ],
    "summary": "Checked 6 extracted parameters across 6 layers: 3 non-compliant finding(s). Final validation remains with the responsible engineer."
  }
}
```

---

### `POST /api/v1/jobs/{job_id}/chat`

Ask the agent about a processed plan. Replies are grounded in the job's
payload, its compliance report, and retrieved regulation excerpts.

`reply` is guaranteed **plain text** (chat-UI safe): LLM agents use a
conversational system prompt, and `ensure_prose()` server-side flattens any
stray JSON and strips markdown markers before the reply leaves the API.

```bash
curl -X POST http://localhost:8000/api/v1/jobs/0c91e588c5b4/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "Check bending radii"}'
```

```json
{ "reply": "Current compliance state:\n- [non_compliant] Cable bending radius: 90 mm (expected >= 150 mm)\n..." }
```

## Data Contract

### `JobStatus`
`queued` · `converting` · `extracting` · `analyzing` · `ready` · `failed`

### `Geometry`
| Field | Type | Notes |
| :--- | :--- | :--- |
| `layer` | string | DXF layer name |
| `kind` | string | `polyline` \| `line` \| `circle` |
| `points` | `[x, y][]` | CAD/world coordinates (Y up); circle → single center point |
| `closed` | bool | closed polylines are treated as areas (rooms/footprints) |
| `radius` | number? | circles only |

### `TextItem`
`layer`, `text`, `position: [x, y]` — plan annotations; mined for electrical
parameters and guideline citations.

### `Metric`
| `name` | Meaning | Unit | Source |
| :--- | :--- | :--- | :--- |
| `room_area` | closed-polyline area | m² | shapely `Polygon.area` |
| `run_length` | open polyline / line length | m | shapely `LineString.length` |
| `cable_bending_radius` | annotated bend radius | mm | regex `R=<n>mm` on texts |
| `cable_pulling_force` | annotated pulling force | N | regex `<n> N` on texts containing "pull" |

### `Finding`
`status` (`compliant` \| `non_compliant` \| `warning`), `parameter`, `actual`,
`expected`, `regulation`, `location?` (layer or coordinates), `suggestion?`.

### `ComplianceReport`
`findings: Finding[]`, `summary: string` (paragraph for the Erläuterungsbericht).
