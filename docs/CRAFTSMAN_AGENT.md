# Craftsman Agent — FreeCAD Geometry Engine (2D ops, DWG in/out)

**Use case:** real 2D CAD geometry editing (offset a cable run, round a
corner) on the originally uploaded plan — not the frontend-only sketch
overlay (`DRAFTSMAN_AGENT.md`), and not the flat add/remove-raw-entities
`POST /jobs/{id}/dwg/manipulate`. The uploaded `.dwg`/`.dxf` goes in, real
geometry ops run, a real `.dwg` comes back out.

## 1. Why this exists

`docs/QCAD_CONNECTOR.md` §5 and `docs/DRAFTSMAN_AGENT.md` §5 both flagged
the same gap: `ezdxf` and `ACadSharp` can author DXF/DWG entities but have
no geometry engine — no offset, fillet, trim, or join. FreeCAD's `Draft`
module has all three (`Draft.offset`, `Draft.make_fillet`,
`Draft.upgrade`/`downgrade`), and it was already sitting one directory over
as a working pixi build (`../FreeCAD-pixi`, confirmed headless via
`FreeCADCmd` with `importDXF` available). This wires it in as a
**geometry-manipulation stage** between the two DWG-boundary pieces this
repo had already benchmarked and trusted — it does not replace either:

```
uploaded .dwg/.dxf --[ensure_dxf, existing]--> .dxf
                   --[FreeCAD worker: upgrade/offset/fillet]--> ParsedDrawing
                   --[AcadSharpEngine.write, existing]--> .dwg
```

v1 scope (by design): **2D ops only** — no pad/extrude, boolean, or STEP
export. This project's plans are 2D rail drawings, not 3D solids. Triggered
by an **explicit ops-list API**, no natural-language instruction parsing yet
(mirrors `POST /jobs/{id}/dwg/manipulate`'s existing shape).

## 2. Architecture

| Piece | File | Role |
| :--- | :--- | :--- |
| Worker | `backend/tools/freecad_worker/worker.py` | Runs *inside* FreeCADCmd's Python. Imports the DXF, runs ops, extracts the result directly into this project's `Geometry`/`TextItem` shape. |
| Bridge | `backend/app/craftsman/freecad_bridge.py` | Subprocess adapter — same shape as `AcadSharpEngine._run`. Finds `FreeCADCmd`, shells out with a timeout, converts the worker's JSON into a `ParsedDrawing`. |
| Config | `Settings.freecadcmd_path` (`app/core/config.py`), `FREECADCMD_PATH` (`.env.example`) | Points at a FreeCAD build — not vendored in this repo, same treatment as the gitignored QCAD clone. |
| Schemas | `CraftsmanOp`/`CraftsmanRequest`/`CraftsmanResponse` (`app/models/schemas.py`) | API contract. |
| Route | `POST /jobs/{job_id}/craftsman` (`app/api/routes.py`) | `ensure_dxf` → `freecad_bridge.run_job` → `AcadSharpEngine.write` → reuses the existing `/dwg/download` route unchanged. |

### Ops (v1)

| Op | Args | FreeCAD call |
| :--- | :--- | :--- |
| `upgrade_objects` | `ids: [str]` | `Draft.upgrade(objs, delete=True)` — joins disconnected DXF edges into closed wires. Needed before offset/fillet on anything that didn't import as one clean wire. |
| `offset_wire` | `id: str`, `delta: [dx, dy, (dz)]` (mm) | `Draft.offset(obj, Vector(*delta), copy=True)`. Note: FreeCAD's `offset` takes a **displacement vector applied to the first vertex**, not a scalar magnitude+direction — the caller picks the direction. |
| `fillet_wire` | `id: str`, `radius`, `edge_indices: [i, j]` | `Draft.make_fillet([obj.Shape.Edges[i], obj.Shape.Edges[j]], radius=...)` — rounds the corner between two adjacent edges of one wire (indices into `obj.Shape.Edges`, discoverable from a snapshot call, see §4). |

Deferred, not silently dropped: `pad_wire` (2D→3D extrude), boolean
union/cut/intersect, `fillet_edges` on solids, `export_step`, `screenshot`.
3D-solid territory this project's 2D compliance pipeline doesn't consume
today.

**Multi-step sequences (`"$prev"`)**: `id`/`ids` may be the literal string
`"$prev"` instead of a real object name, meaning "whatever the previous op
in this same `ops` list just created". This only works *within one call* —
see finding 9 below for why chaining across separate calls doesn't work at
all, and why this had to be a real feature rather than something the caller
fakes client-side.

## 3. Hands-on findings (2026-08-06) — real gaps, not assumptions

Every one of these was hit by actually running the worker against
`backend/data/samples/cad_engine_poc/dummy_project.dxf` and the real
`backend/data/samples/DB/Kreuzungsplan.dwg`, not inferred from docs:

1. **`importDXF.export()` is not the write path, despite being the obvious
   choice.** By default this FreeCAD build's exporter delegates to a
   compiled C++ exporter (`Import.writeDXFObject`) that writes every
   object's **name** as its DXF layer (ignoring the importer's own
   `OriginalLayer` property) and **drops Draft Text objects entirely**.
   Confirmed by exporting and re-parsing with the project's own
   `dxf_parser.parse_dxf`: layers came back as `Polyline`/`Shape`/`Wire`
   instead of `E_ROOM`/`E_CABLE`, and the `R=150mm` annotation vanished.
   For a compliance pipeline that regex-extracts bend-radius/pull-force
   values from exactly that text, this is disqualifying. **Fix**: the
   worker never calls `importDXF.export()` for output — it extracts
   geometry/text directly from FreeCAD's `Shape`/property data into this
   project's own `Geometry`/`TextItem` shape, which the bridge hands
   straight to the already-proven `AcadSharpEngine.write()`. One less
   moving part than the original DXF-export-then-convert plan, and no
   fidelity gap to work around.
2. **Import preferences default text and geometry-joining OFF.**
   `dxftext`/`joingeometry` FreeCAD preferences are `False` by default —
   a fresh import silently drops all TEXT/MTEXT entities and leaves
   LWPOLYLINEs unfused. The worker sets both `True` via `FreeCAD.ParamGet`
   before every import.
3. **Bare single-entity objects have no `Shape.Wires`.** A lone imported
   `LINE` or `CIRCLE` (not part of an LWPOLYLINE) is a `Part::Feature`
   whose `Shape.ShapeType` is `'Edge'`, not `'Wire'` — `Shape.Wires` is
   empty. The first version of the extraction only walked `.Wires` and
   silently lost every bare line/circle in the drawing (caught by the
   geometry count on `dummy_project.dxf` dropping from 5 to 3). Fixed by
   falling back to `Shape.Edges` directly when `.Wires` is empty.
4. **FreeCADCmd treats extra positional args as documents to open, not
   plain `argv`.** Passing job/result paths as CLI args
   (`FreeCADCmd worker.py job.json result.json`) crashes: a `.json`
   argument gets handed to the Fem workbench's YAML/JSON mesh importer
   and throws `FileNotFoundError` before the worker script's own logic
   ever runs. **Fix**: paths travel via `CRAFTSMAN_JOB_PATH`/
   `CRAFTSMAN_RESULT_PATH` environment variables instead.
5. **FreeCADCmd imports the script as a module, not `__main__`.**
   `python worker.py`'s usual `if __name__ == "__main__":` guard never
   fires — FreeCADCmd sets `__name__` to the file's basename. The worker
   calls `main()` unconditionally at module level instead (the same
   convention FreeCAD's own macros use).
6. **No way to discover object ids without a separate listing call.**
   `Geometry`/`TextItem` (the shared `cad_engines` schema) carry no `id`
   field by design — reusing them is what let the bridge skip a second DXF
   round trip (finding 1), but it also means a caller can't tell which
   FreeCAD object to target for `offset_wire`/`fillet_wire` from the
   geometry list alone. Fixed by adding a parallel `objects` field
   (`{id, kind, layer}`, same order as geometries then texts) to both the
   worker's result and `CraftsmanResponse` — call once with `ops: []` to
   get a snapshot, then a real op against the `id` it returned (see §4).
7. **FreeCAD's internal coordinates are 1000x too large for this repo's
   `Geometry` convention.** Found by actually opening a Craftsman result in
   the webapp's CAD viewer (§7) rather than trusting entity-count parity
   alone: the viewer loaded successfully but showed a black, empty canvas.
   Root cause: FreeCAD's document unit is always millimeters internally —
   it rescales on import (the importer logs `Final scaling: 1 DXF unit =
   1000.0000 mm` for a meters-unit source file, which every fixture and
   real plan in this repo is). `Geometry.points`/`TextItem.position`
   elsewhere in this codebase (`dxf_parser.py`, `geometry.py`'s `"m"`/`"m²"`
   metrics) are real-world units matching the source DXF's own `$INSUNITS`
   (meters) - so raw FreeCAD coordinates, used as-is, came out 1000x too
   large (a real plan's true ~140m extent became ~140,000km, invisible at
   any sane auto-fit zoom, though every entity/layer/text was still present
   and correct - this is why finding 1's dual-verification pass, which only
   checked entity counts/kinds/layers/text content, didn't catch it).
   **Fix**: `FREECAD_MM_TO_DOC_UNIT = 0.001` applied at every coordinate
   extraction point in `worker.py` (`_edges_to_geometry`, text position).
   Op *inputs* (`offset_wire`'s `delta`, `fillet_wire`'s `radius`) are
   unaffected - they're applied directly to FreeCAD's native mm space,
   which was always correct.
8. **One DXF `SOLID` entity imported with mirrored coordinates - a real
   plan, not a fixture.** After fixing finding 7, `Kreuzungsplan.dwg`'s
   bounding box matched the original almost exactly except for one
   `VG-BLO-Fahrbahnmarkierung` (road-marking) polyline sitting ~7 million
   units away from every other entity - a FreeCAD DXF-importer bug on that
   specific `SOLID` entity (already wrong in `Shape.BoundBox` before this
   worker's extraction ever runs; `dxf_parser.py` doesn't even represent
   `SOLID` entities, so the production pipeline never had a chance to hit
   this). A single such point is enough to break any "fit everything"
   viewer's auto-zoom for the whole plan. **Fix**: `_drop_coordinate_outliers`
   in `worker.py` - a median + MAD (median absolute deviation) outlier
   guard, robust to a small number of extreme outliers by construction (a
   plain bounding-box or mean/stddev check would itself be dominated by the
   corruption it's trying to catch). Deliberately extreme threshold (200x
   MAD) so it only ever catches this failure mode, never legitimate
   far-from-center geometry. Dropped entities are reported, not silently
   discarded - see the `warnings` field, §4.
9. **A multi-step SOP can't chain object ids across separate
   `POST /craftsman` calls - confirmed by trying it.** The natural first
   design for "run a 3-step remediation SOP" was one API call per step,
   tracking the newly-created object id from each response to target the
   next. It failed at step 2 with `unknown object id 'Face'`: step 1
   (`upgrade_objects` on a closed wire) really did create an object named
   `Face` - but each `POST /craftsman` call opens a **fresh** FreeCAD
   document from the original upload (§1's design, `"each call re-reads
   the original upload"`), so step 2's call never saw step 1's `Face` at
   all. **Fix**: `"$prev"` - a sentinel `id`/`ids` value the worker
   (`tools/freecad_worker/worker.py`) resolves to whatever the previous op
   *in the same `ops` list* created, tracked via a `last_id` threaded
   through `run()`'s op loop. A multi-step SOP is therefore sent as ONE
   call with every step in `ops`, chained with `"$prev"` from the second
   step on - this also sidesteps needing the caller to predict FreeCAD's
   own object-naming (`upgrade` on a closed wire → `Face`, on an open one
   → `Wire`; different types name their outputs differently). See §8.
10. **`Draft.make_fillet(edges, ...)` keeps only the edges it's given -
    it doesn't preserve the rest of the wire.** Filleting a closed 4-edge
    rectangle's corner via `edge_indices: [0, 1]` doesn't return a closed
    4-edge wire with one rounded corner - it returns an **open 3-edge**
    wire made of just [trimmed edge 0, new fillet arc, trimmed edge 1];
    edges 2 and 3 (the other two sides) are silently dropped. Confirmed by
    fillet-then-fillet chaining: every `edge_indices` pair on the result
    (`[0,1]`, `[0,2]`, `[1,2]` - the only three possible on a 3-edge wire)
    fails with "are they adjacent?", because there's no second corner left
    to round, not because the indices were wrong. **Consequence**: a second
    `fillet_wire` can't target a *different* original corner of a wire
    that's already been through one `fillet_wire` call - only offset/join
    ops chain cleanly onto a fillet result. `content/sops.ts`'s 5-step SOP
    was redesigned around this (step 5 is a clearance offset, not a second
    corner fillet) rather than worked around in the worker, since fixing it
    properly means passing `Draft.make_fillet` the whole wire's edge list
    (or reconstructing the untouched edges afterward) - real work, out of
    scope for a v1 whose ops are meant to be composed by a caller who picks
    the right op per step, not assumed fully commutative.

## 4. Using it

```
POST /jobs/{id}/craftsman   {"ops": []}
```
→ snapshot: `objects` (id/kind/layer), `geometries`, `texts`, `layers` —
find the `id` you want to edit (and, for `fillet_wire`, note the object
came in as a single wire whose corner you want — `edge_indices` are
positional indices into that wire's `Shape.Edges`, not exposed directly
today; picking `[0, 1]` for "the first two edges" is the common case for a
simple polyline corner).

```
POST /jobs/{id}/craftsman
{"ops": [{"op": "offset_wire", "id": "Polyline010", "delta": [100, 0, 0]}]}
```
→ `op_results` (per-op ok/detail — a bad id fails that op, not the whole
call), `warnings` (entities dropped for corrupt coordinates — finding 8;
empty on a clean run), then `GET /jobs/{id}/dwg/download` (same route
`/dwg/manipulate` already uses) for the resulting `.dwg`.

Verified end-to-end against real DB data (2026-08-06):
`Kreuzungsplan.dwg` → `offset_wire` on a `VG-BLO-Kabeltiefbau` cable
polyline → downloaded `.dwg`, independently cross-checked two ways
(LibreDWG's `dwgread` structural dump, and a *second* independent
`dwg2dxf` re-conversion re-parsed through the project's own
`dxf_parser.parse_dxf`) — 1387 geometries, 90 texts, all 24 original layers
present, the edited cable layer intact. Same dual-verification discipline
as `CAD_MANIPULATION_ENGINE.md` §3.2: never trust a round-trip through the
same toolchain that wrote it. **This pass only checked entity counts/kinds/
layers/text content, not absolute coordinate magnitude** — findings 7 and 8
(1000x scale, one mirrored entity) both slipped through it and were only
caught by actually opening the result in a real viewer (§7). Re-verified
after both fixes: the Craftsman DXF's bounding box now matches the
original's X/Y extent almost exactly (`(3570517.9, 5731000.7)` –
`(3570657.1, 5731104.6)` both sides, Z flattened to 0 by design — 2D-only,
§1).

## 5. Webapp integration — `/app/roadmap/cad-manipulation-agent`

The roadmap entry for this agent (`webapp/src/content/roadmap.ts`, slug
`cad-manipulation-agent`) now renders a real page
(`webapp/src/pages/CraftsmanAgentPage.tsx`) instead of the static Coming
Soon placeholder every other roadmap item still gets — `RoadmapPage.tsx`
special-cases live slugs via `LIVE_ROADMAP_SLUGS`
(`content/roadmap.ts`, also what fixes the sidebar's "Soon" badge so it
doesn't lie about a shipped feature). Four steps, all real API calls:

1. **Pick a plan** — any uploaded job (`useJobs()`), not gated on the full
   extraction pipeline finishing (Craftsman only needs the raw upload,
   via `_source_path`/`ensure_dxf`, same as `/dwg/manipulate`).
2. **Discover objects** — `POST .../craftsman {"ops": []}`, the snapshot
   pattern from §4.
3. **Run a sample step** — pre-fills a real `offset_wire` op against the
   first discovered geometry object; editable Δx/Δy. This is the
   "sample execution to validate the agent" - it exercises the full
   FreeCAD → new `.dwg` path against whatever real plan the user picked,
   not a canned fixture.
4. **See the result** — `GET /jobs/{id}/craftsman/viewer` (new route,
   `app/api/routes.py`) in an iframe: same cad-viewer/`export_html`
   mechanism as the existing `/jobs/{id}/viewer`, pointed at a DXF
   snapshot of the Craftsman result instead of the original upload.
   `EzdxfEngine().write()` (already used elsewhere in `cad_engines`)
   produces that snapshot alongside the `.dwg` in the same route handler -
   reused, not new write logic. Plus a direct download link for the `.dwg`
   itself (`/dwg/download`, unchanged).

Findings 7 and 8 (§3) were both caught here, not by the API-level
verification in §4 - opening the actual result in a real, pixel-rendering
viewer is a materially stronger check than comparing entity counts, and is
now exactly what step 4 does on every run.

## 6. Why the DWG boundary reuses existing pieces, not FreeCAD's own I/O

FreeCAD can read/write DWG itself only via an external converter (the
`importDWG`/`ODAFileConverter` path) — this repo already has a better-tested
boundary and there's no reason to duplicate it:

- **Read**: `ensure_dxf()` (`app/ingestion/converter.py`, LibreDWG's
  `dwg2dxf`) — already production-proven on all 6 DWG generations in the
  real dataset (`DATASET_INGESTION.md` §5.2).
- **Write**: `AcadSharpEngine.write()` — `CAD_ENGINE_FRAMEWORK.md` §3.2
  benchmarked LibreDWG's own DWG writer (`dxf2dwg`) as broken (0 of 6
  tested versions produced a DWG that was both non-corrupt *and*
  self-readable) and ACadSharp's as reliable (5 of 6, independently
  verified). Craftsman writes through the same proven engine, not a new
  one.

## 7. Limitations & next steps

- **Fillet approximated as a tessellated polyline, not a true arc.** The
  shared `Geometry` schema (`app/models/schemas.py`) has no arc/bulge
  representation (`kind` is `line`/`polyline`/`circle` only, `points` are
  plain XY pairs) — a fillet's rounded corner is sampled into 8 straight
  segments (`ARC_TESSELLATION_POINTS` in `worker.py`) rather than written
  back as a real ARC entity. Visually and dimensionally close, not exact.
  Extending `Geometry` (and `acadsharp_cli`'s C# side) with a bulge/arc
  representation would remove this approximation — out of scope here.
- **No natural-language instruction parsing yet.** Same limitation
  `DRAFTSMAN_AGENT.md` §5 calls out for its own overlay tool — an LLM/
  keyword parser turning "offset this cable run by 150mm" into a
  `CraftsmanOp` (mirroring `app/agent/draftsman.py`'s `_parse_instruction`)
  is the natural next step once the deterministic ops API has real usage.
- **2D only.** `pad_wire`/boolean/`export_step` deferred — see §1.
- **`edge_indices` for `fillet_wire` aren't independently discoverable.**
  The `objects` snapshot gives ids and layers but not per-object edge
  counts/order; today picking `[0, 1]` is a guess for anything but a simple
  wire. A `describe_object(id)` op returning edge count/type would close
  this.
- **The outlier guard (finding 8) treats a symptom, not FreeCAD's root
  cause.** It correctly stops one corrupt `SOLID` entity from breaking the
  whole plan's viewability, but the underlying DXF-import bug in this
  FreeCAD build is still there — a real plan could plausibly hit it on more
  than one entity, or (below the 200x-MAD threshold) not at all, silently.
  Worth an upstream FreeCAD bug report if this recurs; not investigated
  further here since it's a narrow, cosmetic (non-structural-layer) issue
  on this dataset.

## 8. Multi-step SOPs & the workflow canvas (job-scoped pages)

Beyond the roadmap sandbox (§5), the webapp now has a **job-scoped** Node
Runtime page (`/app/jobs/:jobId/craftsman`,
`webapp/src/pages/JobCraftsman.tsx`) reached from a real, editable
n8n-style pipeline canvas (`/app/jobs/:jobId/workflow`,
`webapp/src/pages/JobWorkflow.tsx`, built on `@xyflow/react` - draggable/
connectable nodes, positions and connections persisted per job in
`localStorage`; clicking the Compliance Analyst or Craftsman node routes to
its real page). The canvas's layout is freely editable and is explicitly
*not* a real execution graph - there's no generic node-graph orchestrator
behind it (`CAD_MANIPULATION_ENGINE.md`'s scope decision stands); it's a
planning/reference view over the fixed real pipeline, said so directly in
the page's own copy so it never implies a capability that doesn't exist.

**SOP runner** (`content/sops.ts`, same page): two demonstration SOPs
("Cable Bend-Radius Remediation", 3 steps; "Full Route Realignment", 5
steps), each a real sequence of `upgrade_objects`/`offset_wire`/
`fillet_wire` ops chained with `"$prev"` (finding 9) and sent as one
`POST /craftsman` call. Per-step outcome comes straight from that call's
`op_results` array (index-aligned with the request's `ops`) - the step
chips show `running` for all steps while the one call is in flight, then
`done`/`failed` per step from the response, not a simulated progress bar.
A step whose predecessor failed still runs (worker.py's existing
"continue past a bad op" behavior, §1) against whatever `$prev` last
resolved to - informative for a demo (every step's real outcome is
visible), not silently swallowed.

Verified end-to-end (2026-08-06) against `sample_plan.dxf` from the
Craftsman canvas: dragging a node persists its position across a reload;
clicking Craftsman opens the real FreeCAD viewer full-page; running the
3-step SOP as one call produced `done` on all three steps with `$prev`
correctly resolving `Face` → `Wire` → `Fillet` across the chain; running
the 5-step SOP (after the step-5 redesign, finding 10) produced `done` on
all five steps, `$prev` resolving `Face` → `Wire` → `Wire001` → `Fillet` →
`Offset`.

**React 18 `<StrictMode>` + TanStack Query mutations don't mix well in
dev.** While building the SOP runner, `craftsman.mutate()` fired from a
ref-guarded `useEffect` (guard correctly prevented a second *call*) still
left the mutation's `useMutation` result stuck at `status: "pending"`
forever in the UI - confirmed via the fiber's actual hook state
(`getCurrentResult()`), not just appearance - even though the underlying
`fetch` had genuinely resolved 200 in under a second. Root-caused to
StrictMode's dev-only mount→cleanup→mount effect double-invoke: the
in-flight mutation's observer gets torn down by the simulated unmount
before it can dispatch the settled result to the (same, still-live) fiber.
Confirmed by removing `<StrictMode>` from `main.tsx` - identical code,
same effect, resolves cleanly every time. Since StrictMode's double-invoke
never happens in a production build, this only ever affected the dev
inner loop (it's also what caused the earlier 502-race symptom this
guard was originally added for) - fixed by dropping `<StrictMode>`
entirely rather than working around a dev-only tooling interaction.

## 9. Main Workspace canvas (dashboard simplification)

The sidebar was cut down to Projects / DWG Viewer / Settings - Knowledge
Base, Node Docs, Agents, and the Roadmap section are gone
(`webapp/src/components/layout/Sidebar.tsx`); `/app/roadmap/:slug` itself
stays (still linked from the public `Landing.tsx` marketing page), but
`RoadmapPage.tsx`'s live-page special-case for the old standalone Craftsman
sandbox (`CraftsmanAgentPage.tsx`, `/app/roadmap/cad-manipulation-agent`)
was removed along with the page - every job's Main Workspace canvas has a
real Craftsman node now, making the standalone sandbox redundant.

Per job, the old 5-tab Topbar (Workflow/Data Sources/SOP & Findings/
Craftsman/Console) is gone too - the Workflow canvas (`JobWorkflow.tsx`,
now the job's **Main Workspace**) is the sole hub. Three things changed
there:

- **Template picker.** A job's first-ever visit to Main Workspace (no saved
  `localStorage` layout) shows a "start from" choice - **Compliance Check**
  (Upload→Convert→Extract→Compliance Analyst) or **Editor**
  (Upload→Convert→Extract→Craftsman, with a Knowledge Base connector node
  feeding Craftsman in parallel). Picking one seeds the canvas and persists
  immediately; the picker never reappears for that job.
- **Node palette.** A floating "+ Add node" panel
  (`components/workflow/NodePalette.tsx`) lists every real
  pipeline-stage/agent node, sourced directly from `content/nodeDocs.ts`'s
  `NODE_DOCS` (the same catalogue the old Node Docs page used) rather than
  a duplicated content list. Clicking an entry drops it on the canvas as a
  freeform reference node (no route - only the template-seeded Compliance/
  Craftsman/Data Sources/Console nodes are clickable, see `PipelineNodeData.to`).
  `@xyflow/react`'s `addEdge` already permits cycles with zero code changes,
  so drawing a loop-back connection just works.
- **Hover descriptions.** `PipelineFlowNode.tsx` gained a `description`
  field and a pure-CSS `group`/`group-hover` tooltip (no JS mouse-tracking).
  A new `PipelineFlowEdge.tsx` (`edgeTypes`, same pattern as `nodeTypes`)
  does the same for connections via `EdgeLabelRenderer`, falling back to a
  generic "source → target" label for freeform user-drawn edges.

Persistence changed shape to support this: `localStorage` now stores
`{template, nodes, edges}` (full node objects) instead of `{positions,
edges}` against a fixed node set, since node *identity* is no longer
limited to the old hard-coded `BASE_NODES` array. `loadLayout()` treats a
payload missing `nodes`/`template` (the old shape) as absent rather than
crashing - a job with a pre-existing old-format layout in someone's browser
just sees the template picker again, not an error.

## 10. Live FreeCAD - a real, streamed GUI session

Beyond the lightweight custom viewer (§5, §7), Craftsman can now open the
**real FreeCAD GUI**, streamed into the browser live: the engineer sees the
actual FreeCAD window redraw after every op, not a static reload of an
exported snapshot. "Open live FreeCAD engine ↗" in `JobCraftsman.tsx`'s
viewport header starts it; once active, the SOP runner/manual controls/
action log all keep working unmodified - they just route through the live
session's transport instead of the one-shot one (`api/craftsman.ts`'s
`sendLiveCraftsmanOp` vs `runCraftsman`, same `CraftsmanOp[]` request shape
either way).

### Architecture

```
browser iframe --[xpra HTML5 client, WebSocket]--> xpra server (Xvfb + FreeCAD GUI child)
                                                       |
backend POST .../craftsman/live/op --[plain TCP, JSON]--> live_session.py's op socket
```

- **`backend/tools/freecad_worker/ops.py`** (new) - every op handler and the
  extraction/scaling logic, pulled out of `worker.py` with zero behavior
  change (verified hands-on: identical `op_results`/geometry output
  before/after). Split into three composable pieces instead of one `run()`:
  `open_and_prepare(dxf_path)`, `run_ops(doc, layer_map, ops, last_id)`,
  `extract(doc, layer_map)` - the live session holds `doc`/`layer_map`/
  `last_id` open across many separate requests instead of the one-shot
  path's call-then-discard, and both entrypoints call the identical
  handlers so they can't drift.
- **`backend/tools/freecad_worker/worker.py`** - now a thin CLI wrapper
  (read env vars, call `ops.run(job)`, write the result) - the headless,
  one-shot path used by the SOP runner's fast batch calls (§8) is
  unaffected.
- **`backend/tools/freecad_worker/live_session.py`** (new) - runs *inside*
  the real GUI `FreeCAD` binary (not `FreeCADCmd`), launched the same way
  `worker.py` is (a positional script argument FreeCAD executes on
  startup - confirmed hands-on that this convention carries over from
  `FreeCADCmd` to the GUI binary unchanged). Opens the DXF once and stays
  open for the whole session. **Thread-safety**: a daemon
  `threading.Thread` runs a blocking `socket.accept()` loop that only reads
  JSON off the wire and pushes `(conn, ops)` onto a `queue.Queue()` - it
  never touches `doc`/Draft/Gui objects. A `QtCore.QTimer` (PySide6,
  confirmed the vendored binding hands-on) created on the script's own top
  level - which runs on FreeCAD's Qt main thread, since it's loaded as a
  startup script - polls that queue every 100ms; its callback is the *only*
  place that calls `ops.run_ops`/`ops.extract`/`SendMsgToActiveView
  ("ViewFit")`. This is what makes the GUI redraw live and what makes
  `$prev` persist across every op request for the whole session, not just
  within one call (a real side effect of the persistent document - see §3
  finding 9's "only works within one call" limitation, which live mode
  doesn't have).
- **`backend/app/craftsman/live_bridge.py`** (new) - session manager,
  mirrors `freecad_bridge.py`'s find-the-binary style. **One global session
  at a time** (v1 scope, deliberately - a hackathon demo watched by one
  engineer, not a multi-tenant product): `start_live_session` tears down
  any existing session first. Launches `xpra start <display>
  --start-child="<FreeCAD GUI> live_session.py" --exit-with-children=yes
  --html=on --bind-tcp=0.0.0.0:<port>`, polls the op port until reachable,
  returns the HTML5 client URL. `send_live_op` is a short-lived TCP
  connection per call (write JSON, half-close, read until EOF). Reuses the
  existing `CraftsmanError`/502 convention from `freecad_bridge.py` rather
  than inventing a new status code.
- **New routes** (`backend/app/api/routes.py`, next to the existing
  `/craftsman` routes, same job-lookup/error shape as `craftsman_manipulate`):
  `POST .../craftsman/live/start` → `{html_url}`, `POST .../craftsman/live/op`
  → same `CraftsmanResponse` shape as the one-shot route (also refreshes the
  lightweight viewer/download artifacts, so they stay correct even while
  the engineer is driving the live session), `POST .../craftsman/live/stop`.

### Setup: `xpra` without sudo

No system package manager access was available (no passwordless sudo, no
Xvfb/x11vnc/websockify anywhere) - `xpra` (conda-forge) collapses what
would otherwise be a 4-tool stack (Xvfb + a VNC server + websockify + a
vendored noVNC client) into one tool with a **built-in HTML5 client**,
installable without sudo via a small project-local pixi environment
(`backend/tools/freecad_worker/live_env/`, decoupled from the external
`../FreeCAD-pixi` sibling checkout). Run
`backend/tools/freecad_worker/live_env/setup.sh` once, then set
`FREECAD_GUI_PATH`/`XPRA_PATH` in `.env` (mirrors `FREECADCMD_PATH`'s
existing pattern, including graceful "not configured" degradation - the
live button just 502s with a clear message if unset).

That setup script exists because `pixi install` alone isn't enough - two
real gaps in the conda-forge packages, both found and fixed hands-on:

1. **`xorg-xvfb-server`'s xkeyboard-config data lands in the wrong path.**
   Xvfb failed immediately with "Keyboard initialization failed" - its
   xkeyboard-config data installed to `share/xkeyboard-config-2/` instead
   of the `share/X11/xkb/` layout Xvfb actually looks for at runtime (a
   file-collision "clobber" with another package's partial `share/X11/xkb/`
   - only Xvfb's own `compiled` cache dir survived there). **Fix**: symlink
   `compat/geometry/keycodes/rules/symbols/types` from the real location
   into the expected one.
2. **conda-forge's `xpra` package ships the server only, not the HTML5
   client.** `--html=on` 404s on every path with no bundled `www/` dir -
   the client is a separate, unpackaged repo. **Fix**: vendor
   `github.com/Xpra-org/xpra-html5`'s `html5/` directory into
   `share/xpra/www/` inside the pixi env.

### Other hands-on findings

- **Stuck at "Opening WebSocket connection" forever after restarting a live
  session - root-caused and fixed (2026-08-07).** The very first cold
  start of a live session always worked; clicking "Open live FreeCAD
  engine" a *second* time (stop the running session, start a new one - the
  single-global-session path every subsequent use actually takes) would
  connect the iframe but hang indefinitely at 50% ("Opening WebSocket
  connection"), no error, confirmed reproducible on demand. Isolated by
  injecting a plain `<iframe>` pointing at the *already-running* session
  directly via devtools JS (bypassing the app entirely) - that connected
  fine, proving the session itself was healthy and the bug was specifically
  in the stop→start transition, not iframe embedding or xpra itself. Two
  real gaps in `live_bridge.py`'s readiness/teardown logic, both
  confirmed hands-on:
  1. `start_live_session`'s readiness check (`_wait_for_port`) only waited
     for the **op** port (a raw socket `live_session.py` itself owns) to
     accept a bare TCP connect - never the **HTML/WebSocket** port xpra
     owns. A raw connect succeeding only proves xpra's listener is bound,
     not that its HTTP/WebSocket handling is actually up.
  2. `stop_live_session` ran `xpra stop`/killed the process and returned
     immediately - it never confirmed the old session's ports had actually
     been released before `start_live_session`'s next `xpra start
     --bind-tcp=...` tried to rebind them on the same port.
  **Fix**: `_wait_for_html_ready()` (a real HTTP GET, not just a TCP
  connect) added to the startup readiness gate; `_wait_for_port_closed()`
  added so `stop_live_session` waits for both ports to actually free up
  before returning. Verified fixed both cold (first-ever start) and warm
  (stop-then-start, the path that was actually broken) - both now reach
  "Session started, 100%" cleanly and repeatably.
- **`importDXF.open()` hangs forever under a real GUI, no exception, no
  log line - confirmed by isolating the exact call.** `dxfShowDialog`
  defaults to `True` in FreeCAD's own preferences and only takes effect
  when `FreeCAD.GuiUp` is true (`importDXF.py`'s `if gui and ... hGrp.GetBool
  ("dxfShowDialog", True):` branch, which the headless `FreeCADCmd` path
  never hits since `GuiUp` is always `False` there) - it pops a modal
  `DxfImportDialog` and blocks on `.exec_()` waiting for a click that will
  never come in an automated session. **Fix**: `_set_import_preferences()`
  (`ops.py`, shared by both entrypoints) also sets `dxfShowDialog = False`.
  A silent, exception-free hang like this is exactly why `live_session.py`
  and `live_bridge.py` both write to log files (`/tmp/craftsman_live_
  session_error.log`, `<work_dir>/craftsman_live_xpra.log`) instead of
  relying on console output that isn't always reachable.
- **`$prev` genuinely crosses separate HTTP calls in live mode - verified,
  not just claimed.** Three separate `POST .../craftsman/live/op` calls
  (`upgrade_objects` → `offset_wire {id: "$prev"}` → `fillet_wire {id:
  "$prev"}`), each its own HTTP request/response round-trip, correctly
  resolved `Polyline` → `Face` → `Wire` → `Fillet` across the chain -
  the exact limitation finding 9 (§3) describes for the one-shot path does
  not apply here, because the document never closes between calls.
- **A stuck orphaned xpra/FreeCAD process can become fully unkillable from
  the launching shell.** Hit once while iterating: `ss -tlnp` showed the
  live ports still listening with no `users:` (owning PID) info, `ps`/
  `fuser`/a `/proc/net/tcp` inode-to-`/proc/*/fd` scan all found nothing,
  and killing the parent uvicorn process didn't free the ports either -
  strongly suggesting `xpra`/Xvfb unshares into its own namespace in this
  sandboxed environment, escaping the launching shell's process-tree view
  entirely. `xpra stop <display>` is the reliable way to tear a session
  down (it worked cleanly every time a session was actually tracked); a
  fully orphaned one (from a crashed/interrupted parent) may need a
  different display/port pair rather than more `kill` attempts.
- **The live viewport could connect and run ops correctly while showing a
  blank canvas - root-caused and fixed (2026-08-07).** Against a real DB
  plan (`Kreuzungsplan.dwg`, 1681 objects), the embedded FreeCAD window
  would come up, ops would execute correctly (confirmed via the action
  log), but the 3D view stayed empty. Diagnosed interactively via
  `freecad-cli` (see below) against the *actual* running session instead
  of relaunching xpra per test: `FreeCADGui.ActiveDocument.ActiveView`'s
  camera had `height ≈ 4mm` right after load (the empty-scene default,
  never refit once real geometry existed) or, after a manual `fitAll()`,
  `height ≈ 7.1 billion mm` - because the raw FreeCAD document still
  contains the mirrored-coordinate `SOLID` entity finding 8 already
  excludes from the *API response* (`VG-BLO-Fahrbahnmarkierung` layer,
  BoundBox ~7.1 million meters from every other entity) - `fitAll()`
  operates on the raw document, so that one object's BoundBox dominates
  the fit either way. **The existing `ops.extract`/`_drop_coordinate_
  outliers` point-cloud-based filter doesn't reliably catch the same
  object a raw-BoundBox check does** - confirmed hands-on: on this exact
  session, `ops.extract`'s median/MAD over per-edge points flagged a
  *different*, legitimately-positioned object (`Link_Schacht_1_`) instead
  of the real outlier (`Solid002`). **Fix**: `live_session.py`'s new
  `_hide_boundbox_outliers()` runs the same median+MAD-of-200 approach
  directly against every object's own `Shape.BoundBox` center (not the
  extracted geometry point cloud), hides matches' `ViewObject.Visibility`,
  then fits - independent of, and in addition to, the API-response filter.
  Verified end-to-end: the plan (tracks, roads, a building, annotations)
  now renders automatically at session startup with zero manual steps,
  and stays correctly framed after running real ops.

### Debugging with `freecad-cli` (dev tool, not webapp-facing)

`backend/tools/freecad-cli/` (vendored from
[yoshikouki/freecad-cli](https://github.com/yoshikouki/freecad-cli)) is a
Click CLI that talks XML-RPC to an *already-running* FreeCAD GUI process -
it doesn't launch or manage FreeCAD itself. Its addon
(`addon/FreecadCli/`) starts an XML-RPC server (port 9875) inside whatever
FreeCAD GUI process loads it as a Mod addon - which, once installed, is the
*same* process `live_session.py` already launches for a job's live
session. This makes it a genuinely useful interactive debugging tool: run
`freecad-cli execute-code '...'` against a session the webapp already has
open, instead of relaunching a whole xpra+FreeCAD session per diagnostic
attempt (which is how the blank-viewport bug above finally got isolated in
minutes instead of hours). **It is dev/debug tooling only** - nothing in
the webapp-facing Craftsman agent calls it; the backend's own op transport
(`live_bridge.py`'s socket protocol) is unchanged.

Setup, one-time:
```
cd backend/tools/freecad-cli && uv tool install -e .
mkdir -p ~/.local/share/FreeCAD/v26-3/Mod   # match your FreeCAD build's own
                                             # versioned UserAppDataDir -
                                             # confirmed hands-on this is
                                             # NOT the bare ~/.local/share/
                                             # FreeCAD/Mod path the addon's
                                             # own `install-addon` command
                                             # assumes; check yours with
                                             # `FreeCAD.getUserAppDataDir()`
ln -s "$(pwd)/addon/FreecadCli" ~/.local/share/FreeCAD/v26-3/Mod/FreecadCli
```
Then `freecad-cli ping` / `freecad-cli execute-code '...'` / `freecad-cli
screenshot` work against whatever FreeCAD GUI process is currently running
- confirmed hands-on to be the *exact same, single* process the webapp's
`live/start` route launches (same `ActiveDocument.Name`, same object
count) - no second FreeCAD instance, no extra RAM/CPU.

Three real portability bugs found and fixed in the vendored addon while
getting it working against this repo's custom pixi-built FreeCAD (26.3
dev, not a standard release install):
1. **`InitGui.py`'s `from FreecadCli import rpc_server` failed with "No
   module named 'FreecadCli'"** - this build doesn't put `Mod/` itself on
   `sys.path` before running each addon's `InitGui.py` (only the addon's
   own directory), unlike whatever build the addon was originally written
   against. **Fix**: `InitGui.py` now inserts its own parent directory
   into `sys.path` explicitly.
2. **That fix's first attempt (`os.path.abspath(__file__)`) then failed
   with `NameError: name '__file__' is not defined`** - this build doesn't
   set `__file__` while executing `InitGui.py` either (unlike a normal
   module import). **Fix**: use `inspect.currentframe().f_code.co_filename`
   instead, which survives regardless of how the script was `exec`'d.
3. **`rpc_server.py`'s `from PySide2 import QtCore` failed with "No module
   named 'PySide2'"** - this build vendors **PySide6**, not PySide2
   (already established in §10's Architecture section above for
   `live_session.py`'s own Qt import). **Fix**: try `PySide6` first, fall
   back to `PySide2`.

### Known limitations

- **One global session, not per-job/concurrent** (deliberate v1 scope, see
  above) - starting a second job's live session tears down the first.
- **No auth on `--bind-tcp=0.0.0.0`** - fine for a local, single-user demo
  only; not something to expose beyond localhost as-is.
- **Software rendering, not hardware-accelerated.** `libEGL warning: DRI3
  error: Could not get DRI3 device` appears in the xpra log every session -
  this sandbox has no GPU passthrough to the virtual display, so FreeCAD's
  3D view renders via software (Mesa llvmpipe) rather than hardware GL.
  Functionally fine (confirmed: the GUI initializes, ops run, the session
  streams end-to-end), just slower to redraw than a GPU-backed session
  would be.

## 11. DWG → DXF conversion - pinned to a newer LibreDWG build

`DWG2DXF_PATH` (`.env`) now points at a sibling `../libredwg` checkout's
own build (`build/dwg2dxf`) instead of whatever release happened to be on
`PATH`/`~/.local/bin` - confirmed via `git log`/`--version` to be 113
commits ahead of that installed `0.14` release (`0.14-113-ge0a152d7`),
with real entity-handling fixes in that range (3DLINE stability, `dwg_add_
LINE` rewritten in terms of `dwg_add_3DLINE`). Re-verified the real
`Kreuzungsplan.dwg` conversion end-to-end against the newer build: same
1385 geometries / 90 texts / 24 layers as before, same single outlier
warning (finding 8's mirrored `SOLID`) - no regression, and this also
independently reconfirms finding 8's root cause is on FreeCAD's *DXF
import* side, not LibreDWG's DWG→DXF conversion side (a newer LibreDWG
build didn't change the corrupted entity's presence or shape at all).

Note this is unrelated to FreeCAD's *own* built-in DWG-import preference
(Edit → Preferences → Import-Export → DWG, "Conversion method: LibreDWG",
"Path to file converter") - that setting only matters if you open a `.dwg`
directly inside interactive FreeCAD yourself. This project's pipeline
never does that: `ensure_dxf()` (`app/ingestion/converter.py`) always
converts DWG→DXF with this project's *own* `dwg2dxf` binary first, and
both the headless worker and the live session only ever open the
resulting `.dxf` - confirmed already working correctly end-to-end (1681
objects extracted correctly from the real `Kreuzungsplan.dwg` well before
this pin) even with FreeCAD's own DWG-import preference left unconfigured.

## 12. Debug Console

Sidebar → Dev → Debug Console (`/app/debug`, `webapp/src/pages/DebugConsole.tsx`),
built directly out of the diagnostic loop that found finding 10 above (the
stuck-WebSocket bug) - everything it needed to inspect by hand (real
session health, request timing, xpra's own log) is now always one click
away instead of ad-hoc curl/`ps`/log-tailing each time.

- **Live session card** - not just "does a session object exist": real
  process liveness (`proc.poll()`), uptime, and independent op-port/
  html-port health checks (`live_bridge.session_status()`, reusing the same
  `_wait_for_port`/`_wait_for_html_ready` helpers the startup gate itself
  uses), a link to open the viewer directly, and a stop button.
- **Traffic tab** - every HTTP request the backend has handled (method,
  path, status, duration), recorded by a small ASGI middleware
  (`app/main.py`) into an in-memory ring buffer (`app/core/debug_log.py`,
  last 300 entries - same durability as the rest of this POC, resets on
  backend restart).
- **Commands tab** - every Craftsman op (`headless` or `live` transport),
  with its real `op_results` detail, recorded from both
  `craftsman_manipulate` and `craftsman_live_op` in `routes.py`.
- **xpra log tab** - a tail of `<work_dir>/craftsman_live_xpra.log`, the
  same file `live_bridge.py` already wrote for exactly this kind of
  debugging (finding 10) - now readable without shelling in.

All three data tabs poll every 2s while the page is open
(`webapp/src/queries/useDebug.ts`). New backend routes: `GET /debug/
{session,requests,commands,xpra-log}` - read-only, no auth, same
local-only assumption as the rest of live mode (§10's "Known limitations").
