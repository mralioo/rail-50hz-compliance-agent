# CAD Manipulation Engine — Feasibility, Write Path, and Roadmap to Real Planning

Goal (from partner review of `PROGRESS_REPORT.md`): move past read-only
compliance checking and the frontend-only Draftsman overlay
(`DRAFTSMAN_AGENT.md`) toward **agents that actually manipulate the DWG
file** — generate/edit real CAD geometry from a step-by-step requirement
spec, and verify the result against a ground-truth expectation, producing a
real `.dwg` deliverable an engineer can open.

Branch: `feat/cad-engine-integration`.

> Status legend: ✅ done/verified · 🔄 in progress · ⬜ open

## 1. Question asked: can LibreCAD (installed locally) be the engine?

The user has LibreCAD 2.2.1.2 installed via snap
(`snap info librecad` → "reads DXF/DWG files and writes DXF/PDF/SVG").
Tested hands-on on this machine (2026-07-22), not just read about:

```
$ librecad --help
Usage: librecad [command] <options> <dxf file>
Commands:
  dxf2pdf   Run librecad as console dxf2pdf tool.
  dxf2png   Run librecad as console dxf2png tool.
  dxf2svg   Run librecad as console dxf2svg tool.
```

### Verdict: no — not as an automation engine

| Requirement | LibreCAD reality |
| :--- | :--- |
| Read `.dwg` programmatically | GUI only; the CLI tools (`dxf2pdf/png/svg`) accept **`.dxf` input only** — confirmed by running `librecad dxf2png manual.dwg` → rejected with "Input DXF file" usage error |
| Write `.dwg` | ❌ Not supported at all, GUI or CLI — the snap description itself says "writes DXF/PDF/SVG", `.dwg` is read-only |
| Scripting / automation API | ❌ No CLI flag, no exposed scripting language (unlike QCAD's ECMAScript `-exec`, or FreeCAD's Python `FreeCADCmd`) |
| Reusable library | The 227 MB binary is a single dynamically-linked Qt executable with no separate `libdxfrw.so` exposed — nothing to bind from Python |

**LibreCAD's role in this project: manual visual QA only** — a human opens
a generated `.dwg`/`.dxf` in the real LibreCAD GUI to eyeball it before
trusting it. It is not, and cannot be, part of the automated pipeline. This
extends the existing survey in `CAD_ENGINE_EVALUATION.md` §5.4 ("GUI-first;
DXF via libdxfrw ≈ subset of what ezdxf already gives us"), which evaluated
LibreCAD for *reading*; this round confirms the same is true, more starkly,
for *writing*.

## 2. What the real write engine is

Nothing new to install — the pieces already in the stack cover both
directions:

| Direction | Tool | Status |
| :--- | :--- | :--- |
| DWG → DXF (read) | LibreDWG `dwg2dxf` | ✅ already in production use |
| DXF entities → structured data (read) | `ezdxf` + `shapely` | ✅ already in production use |
| **Structured data → DXF entities (write)** | `ezdxf` (same library, its write API) | ✅ already proven — `scripts/make_sample_dxf.py` has built the demo plan this way since the POC's first commit; just never reused for *agent-driven* writes |
| **DXF → DWG (write-back)** | LibreDWG `dxf2dwg` | 🔄 new this session — `backend/app/ingestion/writer.py`, tested below |

`ezdxf` is a full read/write DXF library, not read-only — the "engine" for
manipulation was already in the dependency tree, just unused on the write
side.

## 3. Hands-on `dxf2dwg` test (2026-07-22) — real findings, not assumptions

Built `backend/app/ingestion/writer.py` (mirrors `converter.py`'s pattern)
and `backend/scripts/cad_engine_poc.py`, which builds two DXF docs with
`ezdxf` and pushes them through `dxf2dwg`:

- `blank_project` — empty doc, just the four standard layers.
- `dummy_project` — a room outline (LWPOLYLINE), a cable run (LINE), a cable
  entry point (CIRCLE), and a bending-radius annotation
  (`TEXT: "NYY-J 5x16 / R=150mm"`) — the same annotation grammar the
  compliance agent's `BEND_RADIUS_RE` already parses.

### 3.1 `--as r2004` — silently drops all geometry ❌

Exits cleanly (`SUCCESS`), but the written DWG is byte-identical in size for
both the blank and the entity-bearing doc. Root cause, from the writer's own
stderr: `ERROR: BLOCK_HEADER * first_owned_entity missing` — the modelspace
block never gets its entities attached. **Do not use r2004 for real content.**

### 3.2 `--as r2000` — writes geometry correctly ✅ (verified independently)

Re-reading the r2000 DWG through our *own* `dwg2dxf` fails
(`ezdxf.recover.readfile` → `ValueError: Invalid handle 0.`) — a bug in
`dwg2dxf`'s DXF-export codepath, triggered by the handle numbering
`dxf2dwg` assigns. That looked at first like "the write is broken," but
isn't: verified with a **second, independent LibreDWG tool**, `dwgread`
(raw DWG → JSON object-tree dump), which has no dependency on `dwg2dxf`'s
DXF exporter:

```
$ dwgread -O json -o dummy.json dummy_project.dwg
SUCCESS
$ grep -o '"LWPOLYLINE"\|"LINE"\|"CIRCLE"\|"TEXT"' dummy.json | sort | uniq -c
      1 "CIRCLE"
      1 "LINE"
      1 "LWPOLYLINE"
      1 "TEXT"
```

All four entities are present in the DWG's object tree. **Conclusion: the
write is good; only our own `dwg2dxf`-based round-trip verification is
unreliable for dxf2dwg's own output.** Don't verify a written DWG by
round-tripping it through the same toolchain's converter — use `dwgread`
(structural check, now in `cad_engine_poc.py`) or a second implementation
(LibreCAD GUI, real AutoCAD) instead.

`writer.py`'s `DEFAULT_DWG_VERSION = "r2000"` reflects this finding.

### 3.3 Fix applied to the read path: `ezdxf.recover.readfile`

`dxf_parser.py` switched from strict `ezdxf.readfile` to
`ezdxf.recover.readfile` — the mode `ezdxf` itself recommends for "files of
unknown origin," which is exactly what any DWG-round-tripped-through-a-
less-mature-writer is. Regression-checked against both existing fixtures
after the change:

- `sample_plan.dxf` → unchanged: 5 geometries, 4 texts, 6 metrics (3
  violations still detected — bending radius 90 mm, pull force 620 N,
  retired citation).
- `Kreuzungsplan.dwg` (real DB data) → unchanged: 38 layers, 946 geometries,
  83 annotations — matches `DATASET_INGESTION.md` §5.4 exactly.

`renderer.py` still uses strict `ezdxf.readfile` — untouched in this pass
(out of scope for the write-engine question), tracked as a gap in §6.

### 3.4 Proof of connectivity to the existing system ✅

The part that actually matters for "real planning": our **own** extraction
pipeline reads a freshly `ezdxf`-authored DXF and recovers the ground-truth
value correctly —

```
metrics: [('room_area', 24.0, 'm²'), ('run_length', 5.831, 'm'),
          ('cable_bending_radius', 150.0, 'mm')]
```

`cable_bending_radius = 150.0mm` was never typed as a number anywhere except
inside the `TEXT` string `"NYY-J 5x16 / R=150mm"` the write engine placed —
the same regex-based extraction the compliance agent runs on real,
human-authored plans runs unmodified on agent-authored ones. This is the
loop a requirements-driven Draftsman needs: **write geometry+annotation →
existing extractor recovers it → existing compliance/metrics code judges
it** — no new read-side code required.

## 4. Open-source DWG engine landscape survey (2026-07-22)

> **Update (2026-07-22, later same day):** the "no open-source engine
> writes DWG reliably" verdict below was research-based caution about
> ACadSharp specifically. Hands-on testing that followed (got it actually
> running against real files, cross-validated against LibreDWG) found the
> opposite for the entity types this pipeline needs — see
> `CAD_ENGINE_FRAMEWORK.md` §3–4 for the full benchmark and the reversed
> recommendation. Left the original text below intact for the record; don't
> treat §4's verdict/recommendation as current — `CAD_ENGINE_FRAMEWORK.md`
> §4 is.

The §3 findings (LibreDWG's writer dropping geometry at r2004, being
described upstream as *"highly experimental and not ready to use yet"*)
raised the obvious question: is there a **more reliable open-source
engine** for a critical, precision-sensitive pipeline? Researched and
compared hands-on-verifiable claims, not marketing copy:

| Engine | License | DWG read | DWG write | Verdict |
| :--- | :--- | :--- | :--- | :--- |
| **LibreDWG** (`dxf2dwg`/`dwg2dxf`, current stack) | GPL, open source | ✅ mature — proven on all 6 DWG generations in our dataset (`DATASET_INGESTION.md` §5.2) | ❌ — upstream maintainers call it experimental; matches the entity-dropping bug found firsthand in §3.1 | Read: yes. Write: no. |
| **ezdxf** (current stack, DXF side) | MIT, open source | N/A — DXF only, by design | N/A | The mature, spec-complete, audited piece (`ezdxf.recover`, `ezdxf.audit.Auditor`) — never touches DWG at all |
| **ACadSharp** (.NET/C#) | MIT, open source | ✅ AC1014–AC1032 | ⚠️ partial — some versions (e.g. AC1021) are read-only | 799 stars, 63 releases, active — but its own docs describe an "extract/modify" design target, **explicitly not lossless round-trip fidelity**. Also means bridging out of the Python stack (subprocess or a microservice), adding an operational surface for no fidelity guarantee in return. |
| **ezdwg** (Rust core + Python API) | MIT, open source | ✅ R14–R2018, decent entity coverage (LINE/ARC/LWPOLYLINE/CIRCLE/ELLIPSE/TEXT/MTEXT/DIMENSION/INSERT/HATCH/SPLINE) | ⚠️ very limited — native writer targets only the old AC1015/AutoCAD2000 format, and only a subset of entities (no INSERT/HATCH/SPLINE writes) | Released ~2026-05, 13 stars, 76 commits. Architecturally the right idea — a real Python API instead of shelling out to a CLI, so no separate-binary round-trip bugs — but too new and too narrow to trust for production write today. Worth re-checking in 6–12 months. |
| **ODA File Converter** | **Not open source** (free-to-use, closed EULA) | ✅ best fidelity available, by consensus | ✅ best fidelity available | The industry-standard answer for DWG fidelity, already wired as our optional fallback read engine (`converter.py`) — disqualifies itself on an open-source-only requirement. |
| LibreCAD/`libdxfrw`, QCAD Community, FreeCAD | GPL/LGPL, open source | Read-decent | ❌ (or GUI-only) | Already ruled out as automation engines in §1 and `CAD_ENGINE_EVALUATION.md` §5.4 — GUI tools, not engines. |

### Verdict

**No open-source engine can currently write DWG with the reliability a
"no errors, must be precise" pipeline requires.** Every write-capable
open-source option either drops content outright (LibreDWG), explicitly
disclaims round-trip fidelity by design (ACadSharp), or covers too narrow a
version/entity range to depend on (ezdwg). This isn't a gap specific to our
stack — it's the state of open-source DWG tooling in general; the one
consistently high-fidelity option (ODA) is free but proprietary.

### Recommendation

Don't chase "which open-source tool writes DWG reliably" — answer a
different, answerable question instead: **treat DXF as the precision engine
of record.** DXF is an open, fully-documented, text-based format, and
`ezdxf` is mature, spec-complete, and carries its own audit/validation layer
— there is no open, dispute-worthy fidelity question on the DXF side.
Concretely:

1. **Generate and edit geometry in DXF via `ezdxf`** — this is where
   correctness is actually verifiable today (§3.4 already proves the
   write→read loop is lossless for our own pipeline).
2. **Keep LibreDWG for the DWG *read* boundary only** — already proven
   reliable, unaffected by the write-side findings above.
3. **Offer `.dwg` only as a best-effort convenience export**
   (`dxf2dwg --as r2000`, per §3.2), never as something compliance-critical
   geometry generation depends on internally. Label it as such in the UI —
   "download as DXF (source of truth)" vs. "download as DWG (best-effort
   compatibility export)".
4. **If a customer contractually needs guaranteed DWG fidelity**, that is
   the one case where reaching for the proprietary-but-free ODA File
   Converter for the write direction too is the honest engineering choice
   over presenting an open-source writer as production-ready.
5. Re-evaluate `ezdwg` once it covers more entity types and DWG versions on
   write — its native-Python-API architecture is the right long-term shape
   for this problem, it just isn't there yet.

## 5. Deliverables from this session

`backend/data/samples/cad_engine_poc/`:

| File | What it is | Verified |
| :--- | :--- | :--- |
| `blank_project.dxf` / `.dwg` | Empty doc, standard 4 layers | ✅ pipeline read confirms 0 geometries (correct); `dwgread` confirms 0 entities |
| `dummy_project.dxf` / `.dwg` | Room + cable run + entry point + `R=150mm` annotation | ✅ pipeline read recovers `cable_bending_radius=150mm`; `dwgread` confirms all 4 entity kinds present in the `.dwg` |

Reproduce: `cd backend && PYTHONPATH=. .venv/bin/python scripts/cad_engine_poc.py`.

**Not yet done:** opening `dummy_project.dwg` in the actual LibreCAD GUI for
a human visual check — no screenshot tooling in this shell session, and it
needs a person looking at a window. Do this manually:
`snap run librecad backend/data/samples/cad_engine_poc/dummy_project.dwg`.

## 6. What's still missing for "real planning by steps + groundtruth"

This session proves the **engine connection** (write → real DWG → our own
system reads it back correctly). It does not yet build the planning
feature itself. Ranked:

1. **Requirement → geometry compiler.** Today's Draftsman
   (`backend/app/agent/draftsman.py`) turns planner clicks into a labeled
   overlay *for display only* — it never calls `ezdxf`'s write API or
   touches a DXF/DWG file. Needs a new code path: structured requirement
   (e.g. "cable route from A to B, min bend radius 150mm, avoid
   `E_CABINET` layer") → `ezdxf` entities + annotations, using the same
   write pattern proven in §3.
2. **Ground-truth verification loop.** The regex-based metric extraction
   (`geometry.py`) already acts as a checker (§3.4) — needs generalizing
   from "parse an annotation string" to "compare a generated plan's metrics
   against an expected/ground-truth spec" (e.g. a JSON requirements file:
   `{"min_bend_radius_mm": 150, "max_pull_force_n": 500, "room_area_m2": 24}`)
   and reuse the existing compliance-agent judgment code rather than a new
   comparator.
3. **`renderer.py` recover-mode fix** (§3.3) — needed once agent-written
   DXF/DWG needs a canvas preview, not just metric extraction.
4. **DWG round-trip fidelity** — `dxf2dwg` r2000 is good enough for a
   best-effort downloadable deliverable today (per §4's recommendation: DXF
   stays the source of truth); if fidelity issues surface in real use
   (modern AutoCAD features, complex blocks), fall back to ODA File
   Converter for the write direction too (currently DWG→DXF only in
   `converter.py`; same wiring pattern extends to DXF→DWG).
5. **API surface.** No endpoint yet exposes "generate/edit geometry and
   emit a `.dwg`" — `POST /jobs/{id}/draw` (existing Draftsman endpoint)
   returns overlay JSON only, never a file. A real-planning endpoint would
   need to return a downloadable artifact (mirrors the existing
   `GET /jobs/{id}/render` file-serving pattern already in `routes.py`).

## 7. Decision record

- **2026-07-22** — LibreCAD evaluated hands-on for the write/automation
  role; rejected (no scripting, no `.dwg` write, CLI is DXF-only
  export) — kept as a manual GUI verification tool only. `ezdxf` (write) +
  LibreDWG `dxf2dwg` (DXF→DWG, `r2000` target) adopted as the write engine,
  proven via a blank + dummy project round trip and independent `dwgread`
  verification. `dxf_parser.py` moved to `ezdxf.recover.readfile` for
  resilience to non-strict DXF (regression-checked against both existing
  fixtures).
- **2026-07-22** — surveyed the open-source DWG engine landscape
  (LibreDWG, ACadSharp, ezdwg) on request, specifically for a
  precision-critical pipeline (§4). Verdict: no open-source engine writes
  DWG reliably today — ACadSharp explicitly disclaims lossless round-trip,
  ezdwg's native writer is too narrow (old-format-only, partial entities).
  **Decision: DXF is the precision engine of record; DWG is a best-effort
  export only**, with ODA File Converter as the fallback if a customer ever
  needs contractual DWG fidelity guarantees. Next: build the
  requirement→geometry compiler (§6.1) on top of this now-proven engine
  connection, targeting DXF output primarily.
- **2026-07-22 (later same day)** — this verdict reversed after actually
  running ACadSharp against real files instead of reading its docs. See
  `CAD_ENGINE_FRAMEWORK.md` for the benchmark and the updated
  recommendation (ACadSharp's DWG write outperforms LibreDWG's).
