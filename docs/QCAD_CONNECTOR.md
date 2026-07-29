# QCAD Connector — Feasibility Investigation (2026-07-25)

Investigation into whether [QCAD](https://github.com/qcad/qcad) (the open-source
2D CAD application) can be wired into the `cad_engines` framework
(`docs/CAD_ENGINE_FRAMEWORK.md`) the same way ACadSharp was: a thin subprocess
connector, not a linked dependency. This is a research spike — nothing has been
built or wired into the pipeline yet.

## 1. What was done

```bash
git clone --depth 1 https://github.com/qcad/qcad.git backend/tools/vendor/qcad
```

Cloned to `backend/tools/vendor/qcad/` (**gitignored**, ~505 MB, GPLv3 source —
never vendor this into the repo; re-clone if experimentation resumes). Inspected
the source tree, `main.cpp`'s CLI arg handling, the ECMAScript action layer, the
bundled `examples/scripts/`, and `src/io/` to answer three questions: can it run
headless, what's the scripting surface, and does it help with DWG (our actual
gap) or just DXF (where we already have ezdxf + ACadSharp).

## 2. License — why a subprocess connector, not a library

QCAD 3 is **GPLv3** (`LICENSE.txt`), with an explicit linking exception
(`gpl-3.0-exceptions.txt`):

> the copyright holders of QCAD give you permission to link the QCAD libraries
> with independent modules to produce an executable or script... and to copy
> and distribute the resulting executable or script under terms of your choice

That exception covers *linking*. We don't link — the connector pattern here
(like ACadSharp's CLI shim) invokes QCAD as a **separate OS process** via
`subprocess`, communicating over files/stdout. That's mere aggregation, not a
combined work: our backend's license is unaffected regardless of the exception.
This is the same reasoning that already applies to invoking LibreDWG's compiled
binaries. Worth stating explicitly since this is a compliance-focused project.

## 3. Headless automation — confirmed, well-documented

QCAD ships a dedicated headless target: `src/console/console.pro` builds
`qcadcmd` (`qcadcmd.com` on Windows), the same app core without a GUI event
loop requirement. The full CLI surface is self-documented in
`scripts/autostart.js`'s `usage()` function:

```
-no-gui                     Don't use GUI. X11: don't connect to X11 server.
-no-show                    Use but don't display GUI.
-autostart [script file]    Run this script instead of scripts/autostart.js —
                             QCAD doesn't start; your script's app runs instead.
-exec [script file] [args]  Execute a script after QCAD starts, args passed through.
-quit                       Quit after executing script(s).
```

Every user-facing action in QCAD (Draw, Modify, File, Edit, ...) is itself an
ECMAScript file under `scripts/`, run through the same JS engine `-autostart`
and `-exec` use (`src/scripting`, Qt Script pre-Qt6 / QJSEngine on Qt6). This
means the *entire* application feature set (fillet, trim, offset, hatch
boundary detection, dimensioning, snap logic) is reachable headlessly, not just
file I/O — this is qualitatively different from ACadSharp/LibreDWG, which only
do read/write.

Confirmed via two bundled examples (`examples/scripts/createdrawing.js`,
`createlayer.js`), run pattern `qcad -autostart examples/scripts/createdrawing.js`:

```js
include("scripts/simple.js");
var doc = createOffScreenDocument();       // in-memory RDocument, no GUI needed
startTransaction(doc);
addLine(0,0, 100,100);
endTransaction();
var di = new RDocumentInterface(doc);
di.exportFile("qcad_createdrawing.dxf");   // RDocumentInterface::exportFile()
```

`RDocumentInterface` (`src/core/RDocumentInterface.h`) exposes what a connector
needs directly:

```cpp
IoErrorCode importFile(const QString& fileName, const QString& nameFilter = "", bool allowEmptyFile = false);
bool        exportFile(const QString& fileName, const QString& fileVersion = "", bool resetModified = true);
```

and `RDocument::queryAllEntities()` / `queryAllLayers()` for reading a loaded
file back out. This is enough surface to write `read.js` / `write.js` connector
scripts mirroring the `acadsharp_cli` pattern — JSON in/out over stdout, driven
by `-autostart`.

## 4. The gap: no DWG in the open-source tree

`CLAUDE.md` (QCAD's own, bundled in the repo) claims `io` handles
"DXF, DWG, PDF, SVG". **This is not true of this repository** — checked:

```
$ ls src/io
CMakeLists.txt  dxf  io.pro
```

Only `dxf/` (`RDxfImporter.cpp`, `RDxfExporter.cpp`, built on the bundled
`dxflib`). No `dwg/` directory, no DWG dependency anywhere in `src/`. DWG
support in QCAD is a **QCAD Professional** feature — a separate, closed-source
sibling project (`qcadpro`, referenced in `CLAUDE.md`'s build script but not
present here) built on a commercial Teigha/ODA license. The open-source `qcad`
repo you get from GitHub is DXF-only.

This matters directly for our use case: **the thing we actually need help
with — DWG read/write reliability — is not something open-source QCAD can do
at all.** ACadSharp already covers that ground (5/6 DWG versions, verified,
per `CAD_ENGINE_FRAMEWORK.md` §3.2).

## 5. Where QCAD would actually add value

Not DWG. Three narrower, real possibilities:

1. **A fourth independent DXF engine for cross-validation.** The benchmark
   methodology in `CAD_ENGINE_FRAMEWORK.md` is built on "never trust one
   engine's self-read of its own write." Right now DXF is only cross-checked
   between ezdxf and ACadSharp. QCAD's DXF importer/exporter (dxflib-based, a
   different, long-lived codebase from both ezdxf and ACadSharp) is a genuine
   third opinion — useful specifically because a critical/precision project
   benefits from an odd number of independent verifiers, not two.
2. **CAD operations we don't have.** ezdxf can author entities but has no
   geometry engine — no trim, offset, fillet, hatch-boundary-from-closed-loop.
   If the Draftsman agent (`docs/DRAFTSMAN_AGENT.md`) ever needs to do more
   than draw raw lines (e.g. "offset this cable run by 150mm", "fillet this
   corner"), QCAD's scripted action layer already implements all of that —
   reimplementing it in ezdxf would be a lot of geometry code we'd otherwise
   have to write ourselves.
3. **Print-quality PDF/PNG export via `PdfExport`/`BitmapExport` scripts**
   (`scripts/File/PdfExport/`, `scripts/File/BitmapExport/`) as a second
   render backend alongside the existing ezdxf+matplotlib renderer
   (`backend/app/extraction/renderer.py`) — lower priority since that renderer
   already resolves INSERT/HATCH/DIMENSION and works well.

None of these are blocking needs right now. This is a "worth knowing it's
there" result, not a "go build this next" result.

## 6. Build feasibility — blocked in this environment

Per QCAD's own `CLAUDE.md`: CMake 3.16+ + Ninja + Qt 6.

```
$ which cmake ninja        # present
$ pkg-config --modversion Qt6Core   → not found
$ apt list --installed | grep qt6   → nothing
```

No Qt6 dev packages are installed, and (as with the earlier .NET SDK install)
this shell has no passwordless `sudo` to `apt-get install qt6-base-dev` etc.
Unlike .NET, there's no official single-script user-space installer for Qt6 —
the practical no-root options are `pip install aqtinstall` (downloads Qt6 into
a user directory) or the prebuilt Linux AppImage QCAD publishes at qcad.org,
neither of which was fetched in this pass since building wasn't requested,
just the feasibility check. Either would need a multi-hundred-MB download —
worth confirming with the user before spending the time/bandwidth.

## 7. Connector — built (2026-07-25, later same day)

Scaffolded and registered, same shape as `AcadSharpEngine`:

- `backend/tools/qcad_connector/read.js`, `write.js` — ECMAScript, grounded
  directly in QCAD's own source (not guessed): the officially bundled
  `scripts/Misc/Examples/CommandLineExamples/ExSetColor/ExSetColor.js`
  (`RMemoryStorage` + `RSpatialIndexSimple` + `RDocument` + `RDocumentInterface`,
  `di.importFile`/`queryAllEntities`/`queryEntity`/`di.exportFile`, the
  `args[args.length-N]` trailing-argument convention) and
  `examples/scripts/createdrawing.js`/`createlayer.js` (the offscreen-document
  `startTransaction`/`addLine`/`addLayer`/`endTransaction` pattern), plus
  `isLineEntity`/`isCircleEntity`/`isPolylineEntity`/`isTextEntity` and
  `readTextFile`/`writeTextFile` from `scripts/library.js`. Consumes/produces
  the same `ParsedDrawing` JSON shape as `acadsharp_cli`, so no schema drift.
  One real finding from reading `RDxfExporter.cpp`: QCAD's DXF writer only
  actually distinguishes two cases internally — R12 (`AC1009`) if the filter
  string contains "R12", else always `AC1015`/R2000 — so `write.js`'s
  `version` argument only meaningfully takes `"r12"` vs. anything else today.
- `QCadEngine(CadEngine)` in `backend/app/cad_engines/qcad_engine.py`:
  `reads_dxf=writes_dxf=True`, `reads_dwg=writes_dwg=False`. Invokes
  `qcadcmd -no-gui -platform offscreen -autostart <script>.js <args> -quit`
  via `subprocess.run`, same 60s-timeout/truncated-stderr pattern as
  `AcadSharpEngine._run`. `-platform offscreen` is QCAD's own documented flag
  for running without an X11 server (`scripts/Tools/arguments.js`'s
  `printGenericUsage()`).
- Registered in `backend/app/cad_engines/registry.py`'s `ENGINES` dict — so
  `scripts/engine_bench.py` picks it up automatically (it iterates
  `ENGINES.items()`, no separate wiring needed) and `imports app.cad_engines`
  confirmed clean: `qcad reads_dxf=True writes_dxf=True reads_dwg=False writes_dwg=False`.
- `QCADCMD_PATH` added to `Settings` (`backend/app/core/config.py`) and
  `backend/.env.example`, following `DOTNET_PATH`/`ACADSHARP_CLI_PATH`.

**Not run against a real `qcadcmd` binary** — still blocked on Qt6/root per
§6, so `find_qcadcmd()` correctly reports `EngineError` ("qcadcmd not
available...") until someone builds it. The JS is grounded in real, working
QCAD source rather than guessed API, but treat it as unverified until
exercised.

## 8. Decision record

- **2026-07-25** — cloned QCAD open-source (GPLv3) to investigate a connector
  into `cad_engines`. Confirmed headless automation via `qcadcmd -autostart`
  is real and well-documented, and the `RDocumentInterface` API is enough to
  write a connector matching the ACadSharp CLI pattern. Confirmed the
  open-source tree is **DXF-only** — `CLAUDE.md`'s "DWG" claim refers to the
  closed-source `qcadpro` sibling project, not this repo, so QCAD doesn't
  close our actual DWG gap. Build blocked locally: no Qt6, no root.
- **2026-07-25 (later same day)** — built the connector scaffold anyway
  (§7): `read.js`/`write.js` + `QCadEngine`, grounded in QCAD's own bundled
  example scripts and source rather than guesswork, registered in the
  `cad_engines` framework. Still unbuilt/unverified locally (no `qcadcmd`
  binary to run against). Same session also wired ACadSharp's DWG read/write
  into a real backend API for the first time (`docs/CAD_ENGINE_FRAMEWORK.md`
  §5.3's "not yet wired into the production pipeline" gap, partially closed)
  and fixed two real bugs it exposed — see that doc's decision record. Left
  the QCAD clone at `backend/tools/vendor/qcad/` (gitignored) for anyone
  picking this back up; safe to delete otherwise.
