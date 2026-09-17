# Session summary — 2026-08-07

Status snapshot, not a spec. Written mid-debugging at the user's request, to
capture what's done and what's left before continuing.

**Update (later same day): the "Known issue" below is resolved.** Root
cause and fix are in `docs/CRAFTSMAN_AGENT.md` §10's "Other hands-on
findings" (the blank-viewport entry) — a raw-BoundBox-based outlier check
in `live_session.py`, found by debugging the live session interactively
via a newly-integrated `freecad-cli` tool (§10's "Debugging with
freecad-cli") instead of relaunching xpra per test. The theory below
(`showMainWindow()` needing a connected client) turned out to be a red
herring for a *different* run's slow startup, not the actual bug.

## Done

### 1. Anvil UI integration (earlier phase, already complete)
Reskinned the webapp around the real backend: job-scoped pages, the
Craftsman agent's viewer, an SOP runner (`content/sops.ts`) chaining
`upgrade_objects`/`offset_wire`/`fillet_wire` via a `"$prev"` sentinel added
to the worker. Fixed two bugs found along the way:
- React `<StrictMode>` was orphaning TanStack Query mutations in dev
  (stuck-`pending` UI) — removed `<StrictMode>` from `main.tsx`.
- `Draft.make_fillet` only keeps the 2 edges it's given, dropping the rest
  of the wire — the 5-step demo SOP was redesigned around this (see
  `docs/CRAFTSMAN_AGENT.md` finding 10).

### 2. Dashboard simplification + Main Workspace canvas + Live FreeCAD
Full plan in `docs/CRAFTSMAN_AGENT.md` §9–§10. Three phases, all implemented
and typechecked/built clean:

- **Phase A** — sidebar trimmed to Projects / DWG Viewer / Settings;
  Knowledge Base, Node Docs, Agents, and the Roadmap section removed from
  nav (routes + pages deleted).
- **Phase B** — the per-job Topbar tab strip removed entirely; the
  Workflow canvas (`JobWorkflow.tsx`) is now the sole per-job hub
  ("Main Workspace"): a template picker (Compliance Check vs Editor) on
  first open, a real node palette (`NodePalette.tsx`, sourced from
  `content/nodeDocs.ts`), and hover tooltips on every node/edge
  (`PipelineFlowNode.tsx`, new `PipelineFlowEdge.tsx`).
- **Phase C** — Craftsman ops can now run against a **real, persistent
  FreeCAD GUI**, streamed into the browser via `xpra`'s HTML5 client,
  instead of only the lightweight one-shot viewer:
  - `backend/tools/freecad_worker/ops.py` — op handlers extracted out of
    `worker.py` (`open_and_prepare`/`run_ops`/`extract`), shared by both
    the one-shot headless path and the new live path, zero behavior change
    (verified against the real worker before/after).
  - `backend/tools/freecad_worker/live_session.py` — runs inside the real
    GUI `FreeCAD` binary, keeps one document open across many op requests
    (socket-accept thread + `QTimer`-drained queue for Qt-main-thread
    safety). This is what makes `$prev` persist across *separate HTTP
    calls*, not just within one call — verified via 3 separate
    `POST .../craftsman/live/op` requests correctly chaining
    `Face → Wire → Fillet`.
  - `backend/app/craftsman/live_bridge.py` + 3 new routes
    (`/craftsman/live/{start,op,stop}`) — session manager, one global
    session at a time (v1 scope).
  - Setup: `backend/tools/freecad_worker/live_env/setup.sh` — installs
    `xpra` via a no-sudo project-local pixi env, with two hand-fixed
    conda-forge packaging gaps (Xvfb's xkeyboard-config path, vendoring
    the xpra-html5 client — neither ships correctly by default).
  - Frontend: `JobCraftsman.tsx` gained an "Open live FreeCAD engine"
    button; once active, the SOP runner/manual controls/action log route
    through the live transport unmodified.

  **This phase's own verification pass at the time (small sample file,
  `sample_plan.dxf`, 9 entities) showed the live FreeCAD window
  connecting, ops executing, and the action log populating correctly.
  It did *not* rigorously confirm visible on-screen geometry — see
  "Known issue" below, found afterward against a much larger real file.**

### 3. Delete project
- `JobStore.delete()` (`backend/app/pipeline/orchestrator.py`) +
  `DELETE /jobs/{job_id}` route — removes the job and its whole
  `work_dir/{job_id}` folder (upload, render, manipulated `.dwg`, viewer
  caches), stops the live session first if it belongs to that job.
- Frontend: `deleteJob`/`useDeleteJob`, a hover-reveal "✕" delete button
  with a `window.confirm` guard on both `ProjectCard.tsx` (Dashboard grid)
  and `JobCard.tsx` (list view).
- Tested end-to-end via curl: job removed from the store, `work_dir`
  folder actually gone from disk, second `GET` correctly 404s.

### 4. Kreuzungsplan.dwg live-FreeCAD demo
Uploaded `dataset/test/Kreuzungsplan.dwg` (job `2f65440e8f5e`) fresh,
opened it in live FreeCAD, selected the real `VG-BLO-Kabeltiefbau`
(cable-trench) route `Polyline010`, and ran the 5-step "Full Route
Realignment" SOP against it through the actual browser UI. All 5 steps
returned `ok: true` with correct chaining:

```
Polyline010 → Wire → Wire001 → Wire002 → Fillet → Offset
```

The session was left running and the tab left open for the user to watch.
**This is where the user then asked "why is the DWG file not displayed in
the FreeCAD engine" — the live FreeCAD window was connected and the ops
genuinely ran (action log proves it), but the 3D viewport itself appeared
visually blank in the screenshot.**

## Known issue — not yet fixed (this is the open thread)

**Symptom:** the embedded live FreeCAD window connects successfully (xpra
HTML5 client reaches "Session started, 100%") and ops execute correctly
against the real document, but the 3D viewport shows no visible geometry.

**Root cause found so far:** isolated a real, reproducible hang —
`FreeCADGui.showMainWindow()` blocks indefinitely when called on a large
document (tested with the real `Kreuzungsplan.dxf`, 1681 objects) **if no
xpra HTML5 client is connected yet at that moment**. Confirmed via a
standalone diagnostic script (`/tmp/view_diag.py`, not committed) run
under xpra with logging:
- With no browser connected: stuck at `showMainWindow()` past 85+ seconds,
  never returns.
- Opening the xpra HTML5 client mid-hang did cause the window title to
  briefly appear ("FreeCAD"), suggesting the call *is* progressing once a
  client is attached — but the test session then disconnected/terminated
  before this could be confirmed as a full fix, and the diagnostic script
  never reached the view-diagnostics code that runs after
  `showMainWindow()` (camera/active-view state, `ViewFit`,
  `viewIsometric`, `fitAll`).

**Why this matters for `live_bridge.py`'s actual startup sequence:**
`start_live_session()` launches xpra with `--start-child=...` and then
polls the **op socket** (`_wait_for_port`) until `live_session.py`'s
threaded op-listener comes up — but the op-listener thread is only
started *after* `showMainWindow()` returns (see `live_session.py`'s
`main()`). If `showMainWindow()` itself depends on a client being
connected, and the backend returns `html_url` to the frontend only once
the op port is reachable, there may be a **startup ordering deadlock**:
the doc-loading/window-showing step could be silently waiting on a client
connection that the frontend hasn't made yet, while the frontend is
simultaneously waiting on the op port (which won't open until
`showMainWindow()` unblocks) before it even shows the iframe pointing the
browser at the HTML5 client. This might explain why the small sample file
(`sample_plan.dxf`) appeared to work — a small document's window
construction may complete fast enough not to expose the race — while the
large real file (1681 objects) makes the hang obvious.

**Not yet confirmed:**
- Whether this theory is fully correct (the last test's session died
  before finishing the diagnostic).
- Whether the fix is: (a) reorder `live_session.py` so the op-listener
  thread starts *before* `open_and_prepare`/`showMainWindow`, so the
  backend/frontend can proceed and the browser connects the HTML5 client
  independent of document-loading progress; (b) pump
  `QApplication.processEvents()` during/after `showMainWindow()` so it
  doesn't need a connected client to unblock; (c) something else entirely
  (e.g. a genuinely large-document-specific slowdown unrelated to client
  connection, and the earlier "FreeCAD" title appearance was coincidental
  timing, not causal).
- Whether, once the window reliably shows, the camera/view actually needs
  an explicit orientation fix (`viewIsometric()`/`viewTop()`) on top of
  `ViewFit`, since flat 2D DXF geometry (all `Z=0`) may render invisible
  under some default camera angles even once the window itself is live —
  this was queued as the next diagnostic step but never reached.

## Next steps

1. Resume the diagnostic: rerun `/tmp/view_diag.py`-equivalent (recreate it
   — it wasn't committed) under xpra **with the HTML5 client already
   connected before the script starts** (reverse of what was tried), to
   isolate whether `showMainWindow()` really needs a pre-existing client
   or whether that was a coincidence.
2. Depending on the result, fix `live_session.py`'s startup ordering (most
   likely: start the op-listener thread and/or defer heavy document
   loading until after the window is confirmed showable) so there's no
   dependency between "browser connects" and "document/window becomes
   ready."
3. Once the window reliably appears, explicitly verify visible geometry —
   add `viewIsometric()`/`viewTop()` before/alongside the existing
   `ViewFit` call in `_fit_view()` if the camera angle turns out to be a
   separate contributing issue.
4. Re-run the Kreuzungsplan.dwg 5-op demo end-to-end and get an actual
   screenshot showing the crossing-plan geometry visibly rendered inside
   the live FreeCAD viewport (not just a successful action log) as the
   real confirmation this is fixed.
5. Clean up: several stray xpra sessions/processes and test ports
   (`:150`–`:153`, port `9911`) were created during this diagnostic session
   and may still need killing; `/tmp/view_diag.py` and its log files were
   never committed and can be discarded or turned into a proper committed
   smoke-test if useful.
6. Once confirmed working, add a short note to `docs/CRAFTSMAN_AGENT.md`
   §10 documenting the real root cause and fix (mirroring that section's
   existing "hands-on findings" style) so this doesn't need
   re-discovering.
