# cad-viewer Integration — Interactive Drawing Viewer + Agent Wiring

Integrates [mlightcad/cad-viewer](https://github.com/mlightcad/cad-viewer) (a
browser-only, MIT-licensed, Three.js/WebGL DXF/DWG viewer+editor) as a second
way to look at a job's plan, alongside the existing static PNG renderer
(`app/extraction/renderer.py`). Locator hits and Draftsman sketches get baked
into the exported drawing as real, highlighted CAD entities — not a raster
overlay.

> Status legend: ✅ done/verified · ⬜ open

## 1. What cad-viewer is, and what we use from it

cad-viewer is a monorepo of npm packages. Two matter here:

- **`@mlightcad/cad-simple-viewer`** — the framework-agnostic core (real
  programmatic API: `AcApEntityService`, `AcApSelectCmd`, live entity
  add/edit/delete). This is the "deep, live-embedded viewer" integration
  path — **not built here**, see §4.
- **`@mlightcad/cad-html-exporter-cli`** — a headless Node CLI (drives
  Playwright/Chromium) that runs the same viewer code path and writes one
  **self-contained offline HTML file**: drawing + viewer runtime embedded,
  opens in any browser, no server, no cad-viewer instance. This is what's
  actually wired in — same "external tool via subprocess" shape as our
  LibreDWG/ACadSharp/QCAD adapters, just Node instead of a native binary.

The library also ships its own generic AI chat agent
(`@mlightcad/cad-agent-plugin` — Vercel AI SDK, client-side OpenAI/Anthropic
keys, `draw_line`/`draw_circle`/etc. tools). **Not used.** Per the scoping
decision below, our own locator/analyzer/draftsman agents stay on the
backend against `DataLayerPayload` and our compliance rules; their output
drives the viewer, rather than adopting a second, separate chat agent.

## 2. Scope decisions (asked up front, both taken)

1. **Lightweight backend export**, not a live-embedded viewer. The backend
   shells out to `cad-html-exporter-cli` to produce a self-contained HTML
   per job/request; the frontend opens it (webview or browser tab). No
   Flutter/JS rewrite, no worker-file hosting, no JS↔Flutter bridge. Trade-
   off: each view is a fresh static export, not a live session the agents
   push updates into mid-session — see §4 for what the deeper option would
   need.
2. **Wire up our own agents**, not cad-viewer's chat plugin. Locator hits
   and Draftsman-drawn elements are injected as real DXF entities on
   dedicated layers before export, so they show up as actual, selectable,
   colored geometry in the interactive viewer.

## 3. DWG licensing — kept DXF-only, verified clean

cad-viewer's **default** DWG parsing path depends on GPL-3.0
`libredwg-web`/`@mlightcad/libredwg-converter`. Unlike our backend's
subprocess-only use of LibreDWG elsewhere (never shipped to a browser), this
would ship as part of the exported HTML artifact if DWG were fed to the
exporter — a real distribution question the library's own maintainers flag
(hence their separate proprietary-parser offering).

Sidestepped it entirely: our pipeline already converts every upload to a
canonical DXF (`app.ingestion.converter.ensure_dxf`), so `export_html()`
never receives a `.dwg`. Verified, not assumed: exported an HTML from a DXF
input and grepped it —

```
$ grep -c "libredwg" /tmp/dummy_project_viewer.html
0
```

— zero occurrences. The GPL DWG parser is only pulled into the bundle when
DWG input is actually used; a DXF-only export stays MIT-clean.

(Aside, found while checking the npm package: `npm view
@mlightcad/cad-html-exporter-cli` reports license `Proprietary`. This is an
npm default for a `package.json` with no `license` field — not an actual
claim — the repo's root `LICENSE` file and this package's own README badge
both say MIT. Noted for anyone else who runs `npm view` and gets alarmed.)

## 4. Architecture

```
backend/tools/cad_viewer_cli/       Standalone npm install of
                                     @mlightcad/cad-html-exporter-cli (not
                                     the whole cad-viewer monorepo - it's
                                     published standalone on npm).
  package.json, package-lock.json   Committed (pins version 1.5.8).
  node_modules/                     Gitignored - `npm install` to restore.

backend/app/viewer/
  cad_viewer_export.py    find_node()/find_exporter_cli() (same
                           settings-override -> PATH -> well-known-local-path
                           pattern as acadsharp_engine.py's find_dotnet()),
                           export_html(dxf_path, out_path, ...): normalizes
                           via ezdxf, then shells out to the exporter CLI.
  annotate.py              build_annotated_dxf(): bakes LocateHit/
                           DrawnElement objects into a copy of the job's DXF
                           as real entities on AGENT_LOCATOR_HIT (yellow) /
                           AGENT_DRAFT (red) layers, via ezdxf directly (not
                           app.cad_engines - see the module docstring for why).

New endpoints in app/api/routes.py:
  GET  /jobs/{id}/viewer            Self-contained HTML, no annotations.
                                     Cached to workdir/{id}/viewer.html.
  POST /jobs/{id}/viewer/annotate   Body: {locate_hits, drawn_elements}.
                                     Builds an annotated DXF, exports fresh
                                     HTML (not cached - input varies),
                                     returns it directly.
```

Why `annotate.py` doesn't go through the `cad_engines` framework:
`ParsedDrawing`/`CadEngine.write()` has no per-layer-color concept (every
engine's write path just does `doc.layers.add(name)`, default color) — that
framework is scoped to engine-agnostic read/write round-trips, not
viewer-specific presentation. Reworking it for one caller's color needs
wasn't worth it; `annotate.py` uses `ezdxf` directly, which the codebase
already depends on everywhere else.

### The deeper option, not built

A live-embedded viewer (`cad-simple-viewer` inside a Flutter webview, JS
bridge, agents calling `AcApEntityService`/`AcApSelectCmd` in real time
instead of triggering a re-export) is the natural next step if the static
per-render export turns out to be too limiting. Needs: a small Vite/TS
bundle, worker-file hosting (DWG/MTEXT workers, ~12MB — moot for us since
we're DXF-only), and a JS↔Flutter bridge (`webview_flutter` or
`flutter_inappwebview`). Not started.

## 5. Setup / reproduce

```bash
# One-time: Node.js 20+ on PATH (this session installed 22.11.0 user-space,
# no root available, same pattern as the .NET SDK install for ACadSharp:
# curl -sL https://nodejs.org/dist/v22.11.0/node-v22.11.0-linux-x64.tar.xz \
#   | tar -xJ --strip-components=1 -C ~/nodejs
export PATH="$HOME/nodejs/bin:$PATH"

cd backend/tools/cad_viewer_cli
npm install
npx playwright install chromium   # downloads ~300MB (Chrome for Testing + headless shell)
```

Then the backend picks it up automatically (`find_node()`/
`find_exporter_cli()`); no `.env` changes needed unless Node/the CLI live
somewhere non-standard (`NODE_PATH`, `CAD_VIEWER_CLI_PATH`).

`node`/`npm` need to be on `PATH` for every shell that runs the backend, not
just the one that ran `npm install` above — either `export PATH="$HOME/nodejs/bin:$PATH"`
per shell, or add that line to `~/.bashrc` once so new terminals pick it up
automatically (interactive shells only — this tool's own non-interactive
shell sessions still need the explicit `export` each time).

## 6. Launch it

### One command

```bash
make viewer                          # opens the upload page - drop any real .dwg/.dxf
make viewer FILE=path/to/plan.dwg    # uploads that file directly, skips the picker
```

`backend/scripts/launch_viewer.sh` does everything by itself:

1. checks deps (venv, `node`, the exporter CLI under
   `tools/cad_viewer_cli/node_modules`, the Playwright chromium cache) and
   prints `[ok]`/`[MISSING]` per item — stops with fix-it instructions if
   anything is missing;
2. starts the backend on `:8000` in the background if it isn't already
   running (health-checked first, so re-running is a no-op there), logs to
   `backend/workdir/backend.log`;
3. with no `FILE=`, opens `GET /api/v1/console` — a drag-and-drop/file-picker
   landing page, no hardcoded sample involved (§9). With `FILE=`, uploads
   that exact file and polls until `ready`;
4. opens the resulting URL in your default browser (`xdg-open`), and prints
   it either way.

Override the port with `PORT=8001 make viewer`. The backend keeps running
after the script exits — `make viewer` again reuses it.

**Gotcha**: the script (and the URL it prints) use `127.0.0.1`, not
`localhost`. Uvicorn only binds IPv4; some browsers resolve `localhost` to
`::1` first and fail to connect before falling back to IPv4. Use
`127.0.0.1:8000/...` if you ever type the URL by hand.

### Manual (what the script automates)

Prerequisites: backend running (`make backend`), §5's setup done, `node` on
`PATH`. This is the exact sequence used to verify the integration live in a
real browser (Chrome, via the claude-in-chrome extension) — not simulated.

```bash
# 1. Create a job from any .dxf/.dwg (any upload already in workdir/ works too)
curl -s -F "file=@backend/data/samples/sample_plan.dxf" \
  http://127.0.0.1:8000/api/v1/jobs
# -> {"id": "23b97bca4685", "status": "queued", ...}   <- note the id

# 2. Wait for the background pipeline (convert -> extract -> analyze) to finish
curl -s http://127.0.0.1:8000/api/v1/jobs/23b97bca4685 | python3 -c \
  "import sys,json; print(json.load(sys.stdin)['status'])"
# poll until this prints "ready" (a few seconds for a small file)

# 3. Fetch the interactive viewer - first call exports it (a few seconds:
#    Chromium startup dominates), cached to workdir/{id}/viewer.html after
curl -s http://127.0.0.1:8000/api/v1/jobs/23b97bca4685/viewer -o viewer.html
```

Then open it:

- **In a real browser**: just navigate to
  `http://127.0.0.1:8000/api/v1/jobs/23b97bca4685/viewer` directly - the
  backend serves the HTML with the right content-type, no need to download
  it first. (Opening the downloaded `viewer.html` as a bare `file://` URL
  also works in a normal browser; some sandboxed browser-automation tools
  refuse to navigate to `file://` URLs specifically, so prefer the `http://`
  endpoint when scripting this.)
- **From the Flutter app**: not wired up yet (§7, item 1) - for now, open
  the URL above in a system browser or a `webview_flutter` panel manually.

To see agent output baked into the viewer instead of a blank/base view, use
the annotate endpoint (`POST /jobs/{id}/viewer/annotate`, documented in §4)
— body is `{"locate_hits": [...], "drawn_elements": [...]}`, response is the
HTML directly, same as the plain `/viewer` endpoint but generated fresh
every call.

## 7. Verified results (2026-07-25)

All of this was actually run, not just planned:

- **Basic export**: `dummy_project.dxf` (the engine framework's synthetic
  fixture) → HTML, screenshotted with headless Chromium — room polyline,
  cable line, circle, and text all rendered correctly, toolbar present.
- **Real pipeline**: uploaded `sample_plan.dxf` through
  `POST /api/v1/jobs`, waited for the background pipeline, called
  `GET /jobs/{id}/viewer` — 200, ~1.2MB self-contained HTML.
- **Agent annotation**: called `POST /jobs/{id}/viewer/annotate` with a
  fabricated locator hit (world bbox around "Schaltraum ÜV 50Hz") and a
  fabricated Draftsman element ("NYY-J TEST CABLE" line) — both appeared in
  the exported viewer as real, colored, selectable entities (yellow box,
  red line + label), confirmed by screenshot.
- **Real-file import failure, root-caused and fixed**: the actual reference
  plan (`Kreuzungsplan.dxf`, 956KB / 1260 entities / DIMENSION, MULTILEADER,
  HATCH, SPLINE, INSERT blocks) failed to import into cad-viewer with
  `Error: Failed to open "Kreuzungsplan.dxf"`, even though `ezdxf.readfile()`
  (strict mode) accepts it without complaint. Bisected by process of
  elimination: it's **not** about DIMENSION or MULTILEADER support
  specifically (removing either alone, or neither, made no difference) — a
  **plain ezdxf read+resave with zero entities touched** fixed it. Some
  structural quirk in the file that ezdxf's writer normalizes away and
  cad-viewer's parser doesn't tolerate; exact byte-level cause not pinned
  down. Fix applied unconditionally in `export_html()` (`_normalize_dxf()`)
  since it's cheap relative to the export itself and turns an intermittent
  real-file failure mode into a handled one.
- **Layer-color bug caught and fixed during testing**: first annotate.py
  draft called `doc.layers.add(name, dxfattribs={"color": N})` — silently
  ignored; ezdxf's `Layers.add()` takes `color` as a **direct keyword
  argument**, not inside `dxfattribs`. Caught because the first screenshot
  showed the highlight/draft entities in default white instead of
  yellow/red. Fixed and re-verified.
- **Config bug reused from the same session's ACadSharp/QCAD work**: the
  blank-`.env`-path-becomes-`Path(".")` bug (see `CAD_ENGINE_FRAMEWORK.md`'s
  2026-07-25 decision record) applies identically to `NODE_PATH`/
  `CAD_VIEWER_CLI_PATH` — already covered by the same `field_validator` fix
  in `app/core/config.py` (both added to `_OPTIONAL_PATH_FIELDS`).

## 8. What's still missing

1. **Flutter frontend wiring.** The Flutter app doesn't call `/viewer` or
   `/console` yet — verified via direct API calls (TestClient +
   headless-Chromium screenshots) in this session, not through the actual
   UI. Simplest first step: a button that opens `GET /jobs/{id}/console` in
   the system browser or a `webview_flutter` panel.
2. **`app/agent/locator.py`/`draftsman.py` don't call `/viewer/annotate`
   automatically** for the Flutter app's own PNG+overlay canvas. The
   browser console (§9) now drives `/viewer/annotate` directly from its own
   JS, so this gap is closed for that surface only - Flutter's
   `plan_viewer.dart` is unaffected.
3. ~~DIMENSION/MULTILEADER/HATCH/SPLINE render fidelity~~ — **verified
   2026-07-30** (§10): the real `Kreuzungsplan.dwg`/`.dxf` (1260 entities,
   including 1 DIMENSION, 3 MULTILEADER, 4 HATCH, 6 SPLINE) renders visually
   correctly end-to-end — dimension line, hatched crossing markings, curved
   rail geometry all present and legible against the matplotlib render as
   ground truth. What was actually blocking this file wasn't entity fidelity
   at all — see §10.
4. **The deep, live-embedded option (§4)** — not started, only scoped.
5. **`export_html()`'s 90s timeout** is untested against a very large real
   DXF under load; the ~3.4s measured is for a tiny synthetic fixture.

## 9. Engineer's Console (2026-07-29)

`GET /jobs/{id}/console` wraps the bare `/viewer` export in a sidebar that
ports the Flutter app's agent-facing features into the browser, plus one
capability Flutter doesn't have. `make viewer` opens this instead of the
bare `/viewer`.

**Loading a real file (no hardcoded plan)**: `GET /api/v1/console` (no job
id) is a separate, job-id-less landing page —
`backend/app/viewer/assets/console_upload.html`, served via
`render_console_upload()` — with a drag-and-drop/file-picker for any real
`.dwg`/`.dxf`. It POSTs to the existing `POST /jobs` upload endpoint, polls
`GET /jobs/{id}` until `ready`, then redirects to that job's `/console`. A
"Recent plans" list (`GET /jobs?limit=`, backed by the new
`JobStore.list_recent()` / `JobSummary` schema — filenames/status only, not
the full payload/report) lets you jump back into an already-processed plan
without re-uploading. Every `console_shell.html` page also has a "Load new
plan" link in its title bar pointing back here, so you can switch files
without leaving the browser. `make viewer` (no `FILE=`) opens this page
directly instead of auto-uploading the bundled sample.

**Architecture**: `backend/app/viewer/console_shell.py` (`render_console_shell`)
substitutes two placeholder tokens (`__JOB_ID__`, `__FILENAME_JSON__` - the
latter via `json.dumps()`, guarding against quote/`</script>` injection from
an uploaded filename) into a static asset,
`backend/app/viewer/assets/console_shell.html` - one hand-written HTML/CSS/JS
file, no build step (this repo has no Jinja2/bundler anywhere). The page
embeds the bare viewer's HTML directly into an `<iframe>` via `srcdoc`
(fetched from `/viewer` on load). All session state (visible locate hits,
accumulated draftsman sketches, chat history, selected knowledge bases)
lives in page-level JS variables - no new backend session storage. Every
locate/sketch/visibility change re-POSTs the *current full state* to the
existing `POST /jobs/{id}/viewer/annotate` and swaps the iframe's `srcdoc`;
rapid changes (e.g. eye-toggle clicks) are debounced ~350ms since each call
is a full Chromium export subprocess.

**Sidebar tabs**:
- **Chat** - free text to `POST /jobs/{id}/chat`, plus 4 preset macro chips
  ("Verify VDE Compliance", "Check Bending Radii", "Generate Explanatory
  Report", "Where is the Schalthaus?"). Client-side regex intent routing
  (ported from `frontend/lib/state/chat_provider.dart`) sends "where is /
  wo / zeig / ..." messages to `/locate` instead, and "draw / zeichne /
  verbinde / ..." messages (when ≥2 sketch points are pending) to `/draw`.
- **Findings** - populated by a locate call: per-hit eye-toggle (re-annotates
  with a filtered `locate_hits` subset), Focus (isolates one hit), Describe
  (`POST /hits/describe`, cached client-side so repeat clicks never re-bill),
  deterministic overview from a batched `POST /hits/analyze` call.
- **History** - `GET /api/v1/searches`, row click re-runs that query through
  the same locate flow.
- **Sketch** - the draftsman tool, reworked for a live 3D viewer: clicks are
  captured on a flat `<img src=".../render">` (not the interactive
  Three.js canvas, which has no exposed raycasting API) and normalized
  directly from the image's own rendered box - no `/render/meta` fetch
  needed, since world-coordinate mapping happens entirely server-side inside
  `/draw`. The resulting sketch is baked into the interactive viewer via
  `/viewer/annotate`, so the final result is real, pannable geometry -
  better than Flutter's raster overlay.
- **Knowledge Base** - new capability, not a Flutter port. Lists named
  regulation corpora (`GET /api/v1/knowledge-bases`) for the engineer to
  scope chat grounding to. See below.

**Knowledge-base filtering** (`backend/app/agent/rag.py`): a "knowledge
base" is a directory grouping under `backend/data/regulations/` - loose
top-level `*.md` files form the `general` KB, each immediate subdirectory is
its own KB (e.g. the pre-existing empty `DB/` → `db`). `list_knowledge_bases()`
walks the filesystem live (not cached) so dropping a file into a KB
directory takes effect immediately. `retrieve(query, kb_ids=...)` filters to
the requested KBs; `kb_ids=None` means the union of *all* KBs - a one-line
widening of the old behavior (`_read_corpus()` used to only glob the
top-level, silently ignoring `DB/`), byte-identical today since `DB/` is
empty. `load_rules()` (ingest-time deterministic checks) intentionally gets
no filter - only the interactive chat path is user-scoped.
`ChatRequest.knowledge_bases: list[str] | None` threads through
`AgentClient.chat()` (all three implementations) into `rag.retrieve()`.
Cognee's memory recall (`app/memory/cognee_store.py`) stays global/unscoped
- dataset-scoping Cognee was judged disproportionate effort for this
iteration, a known limitation rather than an oversight.

**Verified results (2026-07-29)**, via `make viewer` (updated to open
`/console`) + the claude-in-chrome browser extension, same method as §7:

- Console loads, iframe populates with the base viewer, zero console errors
  from our own code (only unrelated `chrome-extension://` noise from the
  automation extension itself).
- Locate → Findings populated → yellow highlight box appeared in the live
  viewer (screenshot-confirmed); eye-toggle off/on correctly added/removed
  the box via re-annotate.
- Describe: deterministic overview + AI description rendered inline;
  confirmed cached (no duplicate network call on a second click).
- **Native layer panel confirmed** - cad-viewer's own toolbar has a Layers
  icon that opens a per-layer checkbox list, including the agent's own
  `AGENT_LOCATOR_HIT` layer. No custom layer-filter UI was built; this
  closes that gap entirely rather than deferring it.
- History: row click correctly re-ran the query and repopulated Findings.
- Sketch → Draw: two clicks on the flat render, a "draw the cable line
  between the points" chat message correctly called `/draw` and baked the
  resulting labeled polyline into the live viewer as real red geometry.
- Knowledge Base tab lists "General" (1 doc) and "DB" (0 docs); confirmed by
  direct backend testing (not just the UI) that `kb_ids=["db"]` returns zero
  retrieved sections while `kb_ids=["general"]`/`None` return the expected
  count.
- **One real bug found and fixed during testing**: sketch-tab click markers
  initially rendered far below the actual click point. Root cause: marker
  `left`/`top` were percentages of `#sketch-wrap` (a scrollable flex
  container much taller than the rendered image), not of the image's own
  box. Fixed by computing marker position from `sketchImg.offsetLeft` /
  `offsetTop` / `clientWidth` / `clientHeight` instead of a wrap-relative
  percentage.

**Still open**: Flutter frontend still doesn't link to `/console` (§8 item
1); per-hit visibility is a full re-annotate round trip rather than a
server-side per-entity toggle (acceptable for a demo, flagged as a future
option if it becomes a bottleneck); Cognee recall is not knowledge-base
scoped (documented limitation above).

## 10. Real-file rendering: blank canvas on large survey coordinates (2026-07-30)

**Symptom**: `data/samples/DB/Kreuzungsplan.dwg` — a real railway crossing
plan, 1260 entities — showed up fine in the Sketch tab's flat PNG render,
but the interactive `/viewer`/`/console` canvas was completely black. No
error banner, no failed network request, no console exception. The toolbar
was interactive and the Layers panel correctly listed every real layer name
from the file, proving the parse itself succeeded.

**Investigation**: the blank-but-no-error signature ruled out the known
"Failed to open" import bug (§7) — that one throws visibly. Inspected the
converted DXF directly with `ezdxf`:

```
$EXTMIN (3570517.934, 5731000.744, ...)   $EXTMAX (3570657.137, 5731104.604, ...)
```

Absolute coordinates in the millions (a real Gauss-Krüger/UTM survey
system), but the drawing itself only spans ~140×104 units. Grepped the
bundled cad-viewer runtime
(`tools/cad_viewer_cli/node_modules/@mlightcad/cad-html-exporter-cli/dist-runner/`):
131 occurrences of `Float32Array` vs. 2 of `Float64Array` — i.e. vertex
positions are uploaded to the GPU as 32-bit floats, standard practice for a
Three.js renderer. `float32` carries ~7 significant decimal digits; at a
magnitude of 3,570,517 that's only ~0.4 units of precision — larger than
this drawing's entire 140-unit extent. Every vertex collapses toward the
same handful of quantized values: geometrically present, logically
correct, and completely invisible.

**Proof, not just a plausible theory**: wrote a one-off script that read
the converted DXF with `ezdxf`, translated every modelspace entity by
`-bbox.center` (via `ezdxf.bbox.extents()`), and re-ran the *exact same*
`export_html()` on the result. The recentered file rendered perfectly on
the first try — full crossing plan, hatched markings, dimension line, curved
rail geometry, trees, buildings. Confirms the diagnosis directly rather
than by inference.

**Fix**: `app/viewer/cad_viewer_export.py::_recenter_if_far()`, called from
`_normalize_dxf()` (the same step that already does the ezdxf recover+resave
from §7's fix) — computes the modelspace bounding box via `ezdxf.bbox`, and
if its center is more than `RECENTER_THRESHOLD_UNITS` (100,000 drawing
units) from the origin, translates every entity by `-center` and updates
`$EXTMIN`/`$EXTMAX` to match. Threshold-gated rather than unconditional so
ordinary already-origin-centered drawings are untouched. Runs *after*
`build_annotated_dxf()` in the `/viewer/annotate` path (both funnel through
the same `export_html()` → `_normalize_dxf()` call), so locator-hit and
draftsman-sketch geometry — baked in using the original, un-recentered
world coordinates — gets translated together with the base geometry and
stays perfectly aligned; no changes needed to `annotate.py`, `locator.py`,
or `draftsman.py`.

**Verified**: re-uploaded the real `.dwg` through the actual running
backend (not just the standalone test script) — `/console` now renders the
full plan. Entities that fail `.translate()` (not every DXF entity type
implements the transform interface) are left in place rather than aborting
the whole export — degrades to one misaligned entity in the rare case,
instead of the current fully-broken state for the whole file.

**What cad or render engine is used, and how to improve rendering further**
(engineer's question, answered in full):

- **Rendering stack**: `@mlightcad/cad-html-exporter-cli` (MIT), a headless
  Node CLI that drives Playwright/Chromium to run `@mlightcad/cad-simple-viewer`
  — a browser-native DXF/DWG viewer built on **Three.js** (WebGL). It is
  *not* a server-side rasterizer; it's the real interactive viewer, snapshotted
  into one self-contained offline HTML file (`AcApHtmlSnapshotBuilder` /
  `packHtml`). Parsing is done by mlightcad's own DXF reader (their AutoCAD-
  object-model layer, `AcDbDatabase`/`AcDbEntity` etc.) — not `ezdxf`; ezdxf
  is only used on our side, before export, for the recover/resave/recenter
  normalization pass.
- **The flat "Sketch" render** (used by the draftsman click-to-sketch tool
  and unaffected by this bug) is a completely different, separate engine:
  `app/extraction/renderer.py`, a `matplotlib` Agg-backend rasterizer that
  reads the DXF via `ezdxf` and draws directly to a PNG. Double-precision
  (`numpy`/Python floats) throughout, hence immune to the float32 issue —
  this is *why* the file "showed in the sketch bar" but not the interactive
  viewer, per the report that triggered this investigation.
- **Improving rendering further, in priority order**:
  1. *(Done here)* Recenter far-from-origin geometry before export — fixes
     outright invisibility, the highest-severity class of rendering bug.
  2. **Precision headroom beyond the threshold**: a single global recenter
     helps any *one* drawing, but a drawing that itself spans >100k units
     (a whole rail corridor rather than one crossing) would still exhaust
     float32 precision even after recentering to its own center. No such
     file has been tested yet; if it comes up, the standard follow-up fix
     is CAD-viewer-side "relative-to-camera" rendering (translate geometry
     by the *camera's* position every frame, keeping GPU-uploaded values
     small) — a change inside cad-viewer itself, not our export pipeline,
     since it needs per-frame camera awareness.
  3. **Entity coverage beyond DIMENSION/MULTILEADER/HATCH/SPLINE** (now
     verified, item 3 above) — ellipses, WIPEOUT, OLE2FRAME, and proxy
     entities from third-party ObjectARX apps are common in real DB Netz
     plans and untested here; worth a pass through more of
     `dataset/test_dwg/` if broader real-world coverage matters.
  4. **`--no-export-invisible-layers`** (an existing exporter CLI flag,
     unused today) would shrink output size for files with many frozen/off
     layers — a size/load-time win, not a correctness one.
  5. The unstarted "deep, live-embedded" option (§4/§8 item 4) would let a
     future version drive the *live* `cad-simple-viewer` API directly
     (selection, live edits) instead of a static HTML snapshot — a much
     larger lift, only worth it if the annotate-and-reload round trip (§9's
     latency note) becomes a real bottleneck rather than a snapshot-refresh
     model being sufficient.

## 11. Decision record

- **2026-07-25** — Investigated github.com/mlightcad/cad-viewer per request.
  Confirmed real, working, MIT-core library with a headless HTML-export CLI
  (`@mlightcad/cad-html-exporter-cli`, Playwright-driven). Scoped to
  lightweight backend export + wiring our own agents (not the library's own
  chat agent), both confirmed with the user before building. Installed
  Node.js 22 user-space (no root, same constraint as the .NET/Qt6 installs
  earlier in this branch's work) and the exporter CLI + Chromium via
  Playwright (~300MB). Built `app/viewer/{cad_viewer_export,annotate}.py`
  and two endpoints. Verified DXF-only keeps the export GPL-clean (grepped
  the output, zero "libredwg" occurrences). Found and fixed two real bugs
  during testing: an ezdxf `Layers.add()` API misuse (color silently
  ignored) and a cad-viewer DXF-import failure on the real reference plan,
  fixed by unconditionally normalizing through ezdxf before export. Not
  done: frontend wiring, and actually calling `/viewer/annotate` from
  locator.py/draftsman.py (§7).
- **2026-07-29** — Built the Engineer's Console (§9): ported the Flutter
  app's chat/locate-highlight/findings/history/draftsman-sketch features
  into a sidebar around the bare viewer, plus a new knowledge-base selector
  (confirmed with the user via AskUserQuestion: named regulation-corpus
  folders, not a literal external DB connection - no new infra). Verified
  live end-to-end via `make viewer` + claude-in-chrome, same method as
  2026-07-25. Confirmed cad-viewer's native layer panel already covers
  per-layer show/hide, closing that gap without new code. Found and fixed
  one real bug during testing: sketch-tab click markers used percentages of
  the scrollable wrap container instead of the image's own rendered box,
  landing far below the actual click point.
- **2026-07-29** — Added the job-id-less upload landing (`GET /api/v1/console`,
  §9) so a real `.dwg`/`.dxf` can be loaded without curl or a hardcoded
  sample file. Added `GET /jobs?limit=` (`JobStore.list_recent()` +
  `JobSummary`) to back its "Recent plans" list, and a "Load new plan" link
  in the console shell's title bar. `make viewer` now defaults to opening
  this landing page instead of auto-uploading `sample_plan.dxf`; `make
  viewer FILE=path/to/plan.dwg` keeps the old one-shot behavior for
  scripting. Verified live: uploaded a real file from the project's
  `dataset/test_dwg/` corpus end-to-end (upload → convert → extract →
  analyze → interactive viewer), and confirmed the "Recent plans" list and
  its click-through both work.
- **2026-07-30** — Root-caused and fixed a real-file rendering bug (§10):
  `Kreuzungsplan.dwg` parsed correctly (layer panel proved it) but rendered
  a fully blank canvas, because its real-world survey coordinates (millions
  of units from origin) exceed cad-viewer's Three.js/float32 vertex-buffer
  precision at the drawing's actual ~140-unit scale. Confirmed by
  reproducing the fix in isolation (recenter + re-export) before touching
  production code. Fixed in `_normalize_dxf()` via a threshold-gated
  recenter so ordinary files are unaffected. This also closes item 3 of §8
  ("What's still missing") — DIMENSION/MULTILEADER/HATCH/SPLINE fidelity
  was never actually the blocker for this file, and is now visually
  confirmed correct.
