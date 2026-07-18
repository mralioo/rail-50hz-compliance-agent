W# Dataset Ingestion & Cognee Memory — Plan and Findings

Goal: process the raw CAD corpus in `dataset/test_dwg/` (130 `.dwg` files,
~96 MB) end-to-end — **convert → extract → refine → summarize (OpenAI) →
store in Cognee memory → chat over it** — and document every step.

> Status legend: ✅ done · 🔄 in progress · ⬜ open

## 1. Plan

| # | Step | Tool / File | Status |
| :-- | :--- | :--- | :--- |
| 1 | Recon: dataset census, env check, converter options, Cognee API | — | ✅ |
| 2 | Build DWG→DXF converter (LibreDWG `dwg2dxf`) | `~/.local/bin/dwg2dxf` | ✅ |
| 3 | Add `dwg2dxf` engine to the ingestion converter | `backend/app/ingestion/converter.py` | ✅ |
| 4 | Batch ingest script: convert + extract + refine each file | `backend/scripts/ingest_dataset.py` | ⬜ (superseded: dataset/test_dwg dropped in favor of `data/samples/DB/`, see §5.4) |
| 5 | Per-file summary via OpenAI | `backend/app/agent/summarizer.py` | ✅ (module ready; used on demand) |
| 6 | Cognee memory bridge + guideline seeding | `backend/app/memory/cognee_store.py`, `scripts/seed_memory.py` | ✅ (see §5.6 and UX_AND_MEMORY.md §3) |
| 7 | Recall wired into agents (chat + describer) | `backend/app/agent/client.py`, `analyzer.py` | ✅ |
| 8 | Update `.env.example` with LLM/Cognee variables | `backend/.env.example` | ✅ |
| 9 | Run against the dataset, record results here | this file §5 | ✅ (per-version smoke test §5.2; full-corpus batch dropped with the dataset) |

## 2. Findings — Reconnaissance

### 2.1 Dataset census (`dataset/test_dwg/`)

130 files, avg ~746 KB, six DWG format generations (magic bytes):

| Magic | AutoCAD version | Count |
| :-- | :-- | --: |
| AC1015 | 2000 | 51 |
| AC1018 | 2004 | 17 |
| AC1021 | 2007 | 36 |
| AC1024 | 2010 | 18 |
| AC1027 | 2013 | 6 |
| AC1032 | 2018 | 2 |

### 2.2 How to convert DWG → DXF (options evaluated)

| Option | Verdict |
| :--- | :--- |
| **ODA File Converter** | Best fidelity, but proprietary; no binary on this machine; download requires manual license acceptance → kept as *optional* engine via `ODA_CONVERTER_PATH` |
| **LibreDWG `dwg2dxf`** | ✅ **chosen.** GPL, reads r13–r2018 (covers the whole census). Not in Ubuntu apt and no Linux release binaries → built from the 0.14 source release (gcc/make present). Known caveat: r2007 (AC1021) reading is the least mature — measured per-version success rate in §5 |
| `ezdxf` alone | Cannot read DWG (DXF only) — that's exactly why a converter is needed |

### 2.3 Environment variables (`.env` check)

Finding: `backend/.env` was an **unmodified copy of the old example — it had
no OpenAI/Cognee parameters at all** (and the root `.env` is empty). Required
additions (now in `.env.example`):

```bash
# Cognee + summarizer — OpenAI is cognee's default provider, so one key serves both
LLM_API_KEY=<your OpenAI API key>        # used by cognee
OPENAI_API_KEY=<same key>                # used by the summarizer
OPENAI_SUMMARY_MODEL=gpt-4o-mini         # cheap + sufficient for 1-paragraph summaries
DWG2DXF_PATH=~/.local/bin/dwg2dxf        # LibreDWG engine (auto-detected if on PATH)
```

⚠️ **Action required:** paste a real OpenAI key into `backend/.env`
(`LLM_API_KEY` + `OPENAI_API_KEY`). Everything else has working defaults.

### 2.4 Cognee (v1.4.0) — API essentials

From <https://docs.cognee.ai/> (installation + quickstart pages):

- `pip install cognee` · Python 3.10–3.14 (we run 3.12 ✓)
- **OpenAI needs only `LLM_API_KEY`** — provider/model/embeddings default to OpenAI
- Default storage is **local, serverless**: SQLite (relational) + LanceDB
  (vectors) + Kuzu (graph) — nothing to deploy for the POC
- Core async API:

```python
import cognee

await cognee.remember(text)                    # ingest → chunk → entities → graph
results = await cognee.recall(query_text=q)    # auto-routed retrieval
await cognee.forget(everything=True)           # reset memory
```

(The older `add()/cognify()/search()` API still exists; `remember/recall`
is the current documented surface.)

## 3. Architecture of the ingestion flow

```
dataset/test_dwg/*.dwg
      │  dwg2dxf (LibreDWG)  →  workdir/dataset/dxf/<name>.dxf
      ▼
parse_dxf() + compute_metrics()          (existing extraction pipeline)
      ▼
refined record (JSON)  →  workdir/dataset/extracted/<name>.json
      │
      ├─► OpenAI summary (1 paragraph per plan)     [skipped if no key]
      ▼
"memory document" (metadata + metrics + texts + summary)
      ▼
cognee.remember()  →  local SQLite/LanceDB/Kuzu under cognee's data dir
      ▼
scripts/memory_chat.py — REPL over cognee.recall()
```

## 4. Usage

```bash
cd backend

# ingest (start small; drop --limit for the full corpus)
.venv/bin/python scripts/ingest_dataset.py --limit 10

# flags: --limit N | --no-llm (skip OpenAI summaries) | --no-memory (skip cognee)
#        --reset (cognee.forget first)

# chat over the ingested memory
.venv/bin/python scripts/memory_chat.py
```

## 5. Run Results

### 5.1 Converter build (2026-07-18)

- **First build attempt "failed" with no real error**: the log showed 0
  compiler errors and 11 `Terminated` lines — the background build was killed
  by session teardown, not by the compiler and **not by weak hardware**
  (i7-1165G7 / 8 threads / 16 GB is ample; the full build takes ~2 min).
  A plain `make` resume completed cleanly → `dwg2dxf 0.14` in `~/.local/bin`.

### 5.2 Conversion + extraction smoke test (1 file per DWG generation)

| File | Version | dwg2dxf | ezdxf parse | Extracted |
| :-- | :-- | :-- | :-- | :-- |
| 07500m1z | AC1015 (2000) | ✅ 548K | ✅ | 3 layers, 666 geometries, 658 metrics |
| 075y8vpo | AC1018 (2004) | ✅ 2.9M | ✅ | 3 layers, **0 geometries** |
| 0754q8oz | AC1021 (2007) | ✅ 272K | ✅ | 2 layers, 15 geometries |
| 075yy8mo | AC1024 (2010) | ✅ 680K | ✅ | 3 layers, 157 geometries |
| 67wlmm81 | AC1027 (2013) | ✅ 1.6M | ✅ | 8 layers, 302 geometries |
| e1gkwpmo | AC1032 (2018) | ✅ 268K | ✅ | 5 layers, 172 geometries |

**Conversion works across all six generations.** Two refinement findings:

1. **0 text entities everywhere** — these real-world plans keep text inside
   block references (`INSERT`/`ATTRIB`), which our parser doesn't traverse yet.
2. **One file yields 0 geometries** — entities are likely old-style
   `POLYLINE`/`ARC`/`INSERT` types outside our current
   LWPOLYLINE/LINE/CIRCLE set.

→ Refinement step for `dxf_parser.py`: handle `ARC`, legacy `POLYLINE`,
`INSERT` (block explosion) and `ATTRIB` text. Tracked as step 4 work.

### 5.3 Cognee verification (2026-07-18)

- SDK **installed and verified**: `cognee 1.4.0` in `backend/.venv`. A live
  round-trip with the OpenAI key from `backend/.env` succeeded —
  `remember()` ingested a plan description and
  `recall("Which plan is a control cabinet layout?")` returned the correct
  plan. Memory runs locally (SQLite/LanceDB/Kuzu), `LLM_API_KEY` is the only
  required variable.
- The user-provided **Cognee Cloud tenant is reachable** (its `/health`
  answers HTTP 200; `COGNEE_API_BASE_URL`/`COGNEE_API_KEY` in `backend/.env`).
  Wiring the SDK to the hosted tenant instead of local storage is part of
  step 6.
- ⚠️ Default data dir currently lands inside
  `.venv/.../cognee/.cognee_system/` — set an explicit data directory when
  building `cognee_store.py` so memory survives venv rebuilds.

### 5.4 New reference sample: `backend/data/samples/DB/Kreuzungsplan.dwg` (2026-07-18)

**Decision: `dataset/test_dwg/` is no longer needed** — the new DB crossing
plan replaces it as the reference real-world input.

- 177 KB, AutoCAD 2018 (AC1032); `dwg2dxf` converts it in 31 ms → 907 KB DXF.
- Extraction: **38 layers, 946 geometries, 83 German annotations** — unlike
  the old test corpus, text lives directly in modelspace
  (“Betonkabelkanal Gr. II/III i.F.”, “HET 2b”, …) with genuine DB layer
  naming (`+EB_Planung`, `+EB_Planung_EEA-Leitungen`, `+EB_Rückbau`,
  `Bestand`).
- Still invisible to the extractor: 214 `INSERT` block references (symbols),
  6 `SPLINE`, 4 `HATCH`, 3 `SOLID`, 1 `DIMENSION` — block traversal remains
  the top refinement item.
- **Fix 1 — prompt size:** the full payload JSON is 243 KB (~62k tokens);
  LLM agents now send a compact digest (`payload_digest()` in
  `app/agent/client.py`: aggregated per-layer metrics + all annotations)
  instead of raw JSON.
- **Fix 2 — hallucinated violations:** the agent initially reported the
  missing bending-radius/pulling-force annotations as `non_compliant`
  (`actual=N/A`). `instruction.md` now mandates: missing data → `warning`
  with `actual="not specified in plan"`, never a violation. Verified: the
  Kreuzungsplan now yields two warnings (add the annotations), while the
  injected-violation sample still yields three `non_compliant` findings.

### 5.5 Cognee memory in production use (2026-07-18)

`COGNEE_ENABLED=true` + seeding via `scripts/seed_memory.py` (regulation
corpus ingested OK). `cognee_store.recall()` verified: returns the 150 mm
bending-radius rule; chat answers now cite guideline memory. Recall latency
~15–25 s per query (LLM-routed) — timeout raised to 30 s; caching is the
next optimization. Full integration details: UX_AND_MEMORY.md §3.

### 5.6 OpenAI compliance agent (2026-07-18)

`AGENT_MODE=openai` added and verified end-to-end on the live server: the
GPT agent (gpt-4o-mini) flags all three injected violations of the sample
plan, writes an LLM summary, and answers chat questions grounded in the
report. `GET /api/v1/health` now returns the active `agent_mode` so a stale
server (started before an `.env` change) is easy to spot.
