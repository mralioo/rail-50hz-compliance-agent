# CAD Engine Framework — Modular Engines, ACadSharp Experiment, Benchmark Results

Follow-up to `CAD_MANIPULATION_ENGINE.md` (which surveyed the open-source
DWG landscape and flagged ACadSharp as worth hands-on testing). This
session: got ACadSharp actually running against real files, and built a
swappable engine framework so any future candidate (or a new LibreDWG/ezdxf
release) can be dropped in and benchmarked the same way, instead of
re-deriving conclusions from scratch each time.

Branch: `feat/cad-engine-integration`.

> Status legend: ✅ done/verified · 🔄 in progress · ⬜ open

## 1. Architecture

```
backend/app/cad_engines/
  base.py               CadEngine ABC + ParsedDrawing (the common currency),
                         EngineError. Capability flags (reads_dwg, writes_dxf,
                         ...) instead of forcing every engine to implement
                         every method.
  ezdxf_engine.py        DXF only. Read delegates to the existing
                         app.extraction.dxf_parser.parse_dxf (one source of
                         truth - the production pipeline and this framework
                         read DXF the same way).
  libredwg_engine.py     DWG via dwg2dxf (read) / ezdxf-write→dxf2dwg (write).
                         LibreDWG is a *converter*, not an entity builder -
                         its write() composes EzdxfEngine + dxf2dwg and says
                         so in the docstring, rather than pretending to be a
                         native DWG writer.
  acadsharp_engine.py    DWG + DXF, both directions, natively - shells out to
                         tools/acadsharp_cli (see §2).
  qcad_engine.py          DXF only (QCAD's open-source tree has no DWG I/O -
                         see docs/QCAD_CONNECTOR.md). Shells out to `qcadcmd`
                         running tools/qcad_connector/*.js. Scaffolded and
                         registered but unbuilt/unverified locally (no Qt6).
  manipulate.py           apply_edits(ParsedDrawing, list[DwgEditOp]) - the
                         edit logic behind the /dwg/manipulate API endpoint
                         (§5.3), engine-agnostic and independently testable.
  registry.py            ENGINES dict + get_engine(name) - the thing
                         scripts/engine_bench.py (or, later, config-driven
                         engine selection) iterates.

backend/tools/acadsharp_cli/    .NET 8 console app, source in Program.cs.
  Commands: read <in> <out.json> | write <spec.json> <out> [version]
            | convert <in> <out> [version]
  JSON interchange format (camelCase) mirrors ParsedDrawing exactly, so the
  Python adapter does no field translation.

backend/scripts/
  cad_engine_poc.py      (prior session) blank/dummy project + connectivity
                          proof - unchanged, still the "hello world" fixture.
  engine_bench.py         NEW - runs every registered engine through read /
                          write / cross-read-back tests, prints a comparison
                          table, writes data/samples/cad_engine_poc/
                          bench_results.json. This is the "test and change
                          module to find the best combination" tool.
```

Why a subprocess for ACadSharp and not a Python↔.NET bridge (`pythonnet`):
ACadSharp is .NET/C#; this backend is Python. A small, purpose-built CLI
(`tools/acadsharp_cli/Program.cs`, ~230 lines) is simpler and lower-risk for
an experiment than embedding the CLR in the FastAPI process. Same pattern
already used for LibreDWG's `dwg2dxf`/`dxf2dwg` - one more external-tool
adapter, not a new architectural idea.

## 2. Getting ACadSharp running (2026-07-22)

- **.NET 8 SDK**: not installed; no passwordless `sudo` in this shell for
  the apt package, so installed user-space via Microsoft's official
  `dotnet-install.sh` into `~/.dotnet` (same non-root pattern already used
  for LibreDWG's from-source build). `dotnet --version` → `8.0.423`.
- **`tools/acadsharp_cli`**: new .NET console project, `PackageReference
  Include="ACadSharp" Version="3.6.35"` (latest stable on NuGet at time of
  writing). Built clean on the first `dotnet build -c Release` - no API
  surprises, once cross-checked against the library's own
  `src/ACadSharp.Examples/` folder on GitHub for the exact class/method
  shapes (`DwgReader.Read`, `DwgWriter`, `DxfWriter`, `CadDocument.Entities`,
  `LwPolyline(IEnumerable<XY>)`, `Layer`, `TextEntity.Value` via the `IText`
  interface, `ACadVersion` enum values `AC1015`…`AC1032`).
- Build output (`bin/`, `obj/`) and the CLI's dependencies are gitignored;
  reproduce with `cd backend/tools/acadsharp_cli && dotnet build -c
  Release`. `DOTNET_PATH`/`ACADSHARP_CLI_PATH` env vars override
  auto-detection (`.env.example`), same pattern as `DWG2DXF_PATH`.

## 3. Benchmark results (2026-07-22, reproducible via `scripts/engine_bench.py`)

Fixtures: `sample_plan.dxf` (demo plan), `Kreuzungsplan.dwg` (real DB data,
38 layers / 946 geometries / 83 annotations), and a synthetic "dummy"
drawing (room polyline + cable line + circle + `R=150mm` annotation) written
at every DWG version LibreDWG's tooling names (`r2000`…`r2018`) by every
engine that can write it, then **read back by every engine that can read
that format** - not just the engine that wrote it, so a corrupt-but-
self-consistent file can't hide.

### 3.1 Read fidelity — exact match across engines ✅

| Fixture | Engine | Result |
| :--- | :--- | :--- |
| `sample_plan.dxf` | ezdxf | layers=6 geoms=5 texts=4 |
| `sample_plan.dxf` | acadsharp | layers=6 geoms=5 texts=4 (identical) |
| `Kreuzungsplan.dwg` (real) | libredwg | layers=38 geoms=946 texts=83, 0.287s |
| `Kreuzungsplan.dwg` (real) | acadsharp | layers=38 geoms=946 texts=83 (identical), 0.280s, **no DXF intermediate step** |

ACadSharp reads the real reference plan directly (DWG in, structured data
out, one process) and matches our production LibreDWG+ezdxf pipeline
exactly, at the same speed.

### 3.2 DWG write × read-back matrix — the important result

| Version | Writer | Write | Self-read | Cross-read (other engine) |
| :--- | :--- | :--- | :--- | :--- |
| r2000 | libredwg | ✅ 5.4KB | ❌ `ValueError: Invalid handle 0.` | ✅ acadsharp reads it fine (geoms=3/3) |
| r2000 | acadsharp | ✅ 7.9KB | ✅ | ✅ libredwg's `dwg2dxf` reads it fine |
| r2004 | libredwg | ✅ *(1.6MB, bloated)* | ⚠️ reads but **0/3 geometries** — entities dropped | ❌ acadsharp: `ArgumentException: duplicate key` — genuinely malformed, not just empty |
| r2004 | acadsharp | ✅ 9.5KB | ✅ | ✅ libredwg reads it fine |
| r2007 | libredwg | ❌ dxf2dwg errors on DIMSTYLE/LTYPE | — | — |
| r2007 | acadsharp | ❌ `CadNotSupportedException: File version not supported: AC1021` | — | — |
| r2010 | libredwg | ✅ *(573KB, bloated)* | ⚠️ 0/3 geometries | ❌ acadsharp: duplicate-key crash |
| r2010 | acadsharp | ✅ 10.7KB | ✅ | ✅ libredwg reads it fine |
| r2013 | libredwg | ✅ *(303KB, bloated)* | ⚠️ 0/3 geometries | ❌ acadsharp: duplicate-key crash |
| r2013 | acadsharp | ✅ 10.7KB | ✅ | ✅ libredwg reads it fine |
| r2018 | libredwg | ✅ *(303KB, bloated)* | ⚠️ 0/3 geometries | ❌ acadsharp: duplicate-key crash |
| r2018 | acadsharp | ✅ 10.7KB | ✅ | ✅ libredwg reads it fine |

**LibreDWG `dxf2dwg`: 0 of 6 tested versions produce a DWG that is both
non-corrupt (confirmed by a second, independent reader) and self-readable.**
r2000 contains real geometry (proven by ACadSharp reading it) but crashes
`dwg2dxf`'s own re-read. r2004/r2010/r2013/r2018 are worse than last
session's finding suggested — not merely "entities dropped" but
structurally malformed enough to also crash ACadSharp's independent parser.
r2007 fails outright. This is a stronger, more complete indictment than
`CAD_MANIPULATION_ENGINE.md` §3 captured (that session only checked r2000
and r2004; this one checked all six and cross-validated every result against
a second implementation instead of trusting either engine's self-read).

**ACadSharp: 5 of 6 versions write cleanly and round-trip losslessly**,
verified two ways (self-read and LibreDWG's independent `dwg2dxf`) at every
successful version. The one failure (r2007/AC1021) fails *declaratively* —
a typed exception naming the exact unsupported version — not silently, and
matches the library's own documented limitation (AC1021 write unsupported).

### 3.3 DXF write — both engines, fully cross-compatible ✅

`ezdxf` and `acadsharp` DXF writes are both read correctly by both readers
(`ezdxf`, `acadsharp`) — no surprises on the DXF side, consistent with DXF
being an open, well-specified text format.

### 3.4 Timing

| Engine | Typical call | Notes |
| :--- | :--- | :--- |
| ezdxf | 6–10 ms | in-process, no subprocess overhead |
| libredwg | 6–13 ms (tiny files), 287 ms (946-geometry real plan) | native compiled binary, scales with file complexity |
| acadsharp | ~190–280 ms, roughly flat regardless of file size | dominated by `dotnet` process/JIT startup, not by the actual read/write work — an AOT-compiled or long-running-process build would likely cut this substantially if it ever matters |

None of these are anywhere near a bottleneck for a user-triggered action
(upload, or a Draftsman write) — the ~200ms ACadSharp overhead is a fixed
cost per subprocess call, not a scaling problem.

## 4. Updated recommendation (supersedes `CAD_MANIPULATION_ENGINE.md` §4's caution)

That earlier survey correctly reported ACadSharp's own documentation
disclaims "lossless round-trip fidelity" as a general design stance, and
recommended treating DXF as the source of truth partly on that basis. Hands-
on testing changes the picture for the entity types this pipeline actually
needs (LINE, LWPOLYLINE, CIRCLE, TEXT — exactly what `dxf_parser.py`
extracts): **ACadSharp's DWG write is the most reliable engine tested so
far, open-source or not**, beating both LibreDWG (broken write) and the
earlier assumption that only the proprietary ODA converter could be trusted.

Revised guidance:
1. **ACadSharp becomes the primary candidate for both DWG read and DWG
   write**, pending the same test against a wider entity set (HATCH,
   SPLINE, INSERT/block traversal — see §5).
2. **DXF remains a fine, mature, boring choice** for the entity-authoring
   step itself (`ezdxf`) — no reason to change that half.
3. **LibreDWG's role should narrow to DWG *read* only** in production code
   — its write path (`dxf2dwg`) is now empirically the least reliable
   option available, not just "experimental" per upstream's own wording.
   `app/ingestion/writer.py` and `LibreDwgEngine.write()` stay in the
   framework for benchmark comparison, not as the recommended default.
4. This doesn't retroactively make ODA unnecessary — it's still untested
   here (no local binary, license-gated) and remains the fallback if a
   customer needs guarantees beyond what any of these three deliver.

## 5. What's still missing

1. **Entity coverage.** Both `EzdxfEngine`/`AcadSharpEngine`'s write side
   only handle LINE/LWPOLYLINE/CIRCLE/TEXT — the same subset
   `dxf_parser.py` reads. Real plans also have HATCH, SPLINE, DIMENSION,
   and (most importantly per `DATASET_INGESTION.md`) `INSERT`/block
   references. ACadSharp's reader already surfaces these (see the `Insert`
   type used in its own examples) — extending `acadsharp_engine.py`'s
   `read()` to decode blocks would be a genuine capability gain over the
   current pipeline, independent of the write-engine question.
2. **LibreCAD visual QA, still manual.** No screenshot tooling in this
   shell session (per `CAD_MANIPULATION_ENGINE.md` §1) — opening an
   ACadSharp-written `.dwg` in the actual LibreCAD GUI as a fourth,
   completely independent sanity check hasn't been done by a human yet.
3. **Partially wired into the production pipeline (2026-07-25).** The main
   extraction pipeline (`pipeline/orchestrator.py::run_pipeline`) still calls
   `ingestion/converter.py` + `extraction/dxf_parser.py` directly, unchanged
   — that's the working demo path and stays untouched by design. What's new:
   a *separate* set of endpoints (`GET /jobs/{id}/dwg`,
   `POST /jobs/{id}/dwg/manipulate`, `GET /jobs/{id}/dwg/download` in
   `app/api/routes.py`) that read/edit/write the originally uploaded file
   directly through `cad_engines`, independent of the pipeline's
   `DataLayerPayload`. Config-selectable production read path
   (`CAD_READ_ENGINE=libredwg|acadsharp`) is still not done.
4. **`.dwg` write is now reachable from the API (2026-07-25).** The gap noted
   in `CAD_MANIPULATION_ENGINE.md` §6.5 is closed for the manipulate flow
   above: `POST /jobs/{id}/dwg/manipulate` writes a real `.dwg` via
   `AcadSharpEngine` and `GET /jobs/{id}/dwg/download` serves it. Verified
   end-to-end against a real DWG fixture, including an independent
   LibreDWG re-read of the written file (not just ACadSharp's own re-read) —
   see §7's 2026-07-25 entry. Not yet wired into the Draftsman agent or
   frontend UI — those still only touch the render/overlay layer.
5. **ODA File Converter untested here** — no binary on this machine, still
   only evaluated on paper (§4.4).

## 6. Reproduce

```bash
# one-time: build the ACadSharp CLI shim (needs .NET 8 SDK)
cd backend/tools/acadsharp_cli && dotnet build -c Release

# run the full benchmark
cd backend && PYTHONPATH=. .venv/bin/python scripts/engine_bench.py
```

Prints a comparison table and writes
`data/samples/cad_engine_poc/bench_results.json` (gitignored — regenerate,
don't rely on a stale committed copy).

## 7. Decision record

- **2026-07-22** — Installed .NET 8 SDK (user-space, `dotnet-install.sh`,
  no `sudo` available). Built `tools/acadsharp_cli`, a thin CLI wrapper
  around ACadSharp 3.6.35. Built the `app/cad_engines/` modular framework
  (`CadEngine` ABC, `ParsedDrawing`, registry) wrapping all three engines
  (ezdxf, LibreDWG, ACadSharp) behind one interface, plus
  `scripts/engine_bench.py` to compare them on demand. Ran the full
  write×version×cross-read matrix on real and synthetic fixtures.
  **Finding: ACadSharp's DWG write is more reliable than LibreDWG's across
  every version tested (5/6 clean + independently-verified round trips vs.
  0/6), reversing the cautious "DXF only" recommendation from
  `CAD_MANIPULATION_ENGINE.md` §4** for the entity subset this pipeline
  uses. Not yet wired into the production pipeline (§5.3) — next step if
  this direction is confirmed.
- **2026-07-25** — Added `QCadEngine` (DXF-only, unbuilt/unverified locally —
  see `docs/QCAD_CONNECTOR.md`) and, separately, three API endpoints
  (`GET /jobs/{id}/dwg`, `POST .../dwg/manipulate`, `GET .../dwg/download`)
  that read/edit/write the originally uploaded DWG/DXF straight through
  `cad_engines`, closing §5 items 3-4. Building and exercising this against a
  real DWG surfaced two real, pre-existing bugs, both fixed:
  1. `Settings`' optional path fields (`DOTNET_PATH`, `ACADSHARP_CLI_PATH`,
     etc.) were parsed from a blank `.env` line as `Path("")` ==
     `Path(".")` — truthy and `.exists()` (it's cwd) — so `find_dotnet()`
     silently "found" the working directory instead of correctly treating
     the setting as unset, and every subprocess call failed with a
     confusing `PermissionError: Permission denied: '.'` instead of the
     intended `EngineError`. Fixed with a `field_validator` in
     `app/core/config.py` that normalizes blank/whitespace env strings to
     `None` for all six path settings.
  2. `acadsharp_cli`'s `BuildDoc` (`tools/acadsharp_cli/Program.cs`) called
     `doc.Layers.Add()` unconditionally for every layer in the spec — fine
     for the benchmark's synthetic fixtures, but a real DWG always has a
     default `"0"` layer already present in a fresh `CadDocument`, so any
     read-then-write round trip of a real file threw
     `ArgumentException: An item with the same key has already been added`.
     Fixed by reusing the existing layer object when one already exists.
  Verified the full loop end-to-end: uploaded a real DWG, read it via the
  new endpoint, added a line + text, removed a circle, wrote a new DWG, and
  **independently cross-read the result with LibreDWG** (not just
  ACadSharp's own re-read) — geometry and text counts matched.
