# Frontend Guide — Planner's Playground

Flutter desktop app (package `planner_playground`) implementing the
three-panel planner workstation from `frontend/FLUTTER_PLAYGROUND_SPEC.md`.
Scaffolded for **Linux, macOS, Windows, and web**.

## Panel Layout

```
┌──────────────────────────────────────────────┬────────────────────┐
│  PipelineStatusBar (always visible)          │                    │
│  ──────────────────────────────────────────  │   AgentConsole     │
│  WorkspacePanel                              │   - chat history   │
│    FileDropZone   (no file yet)              │   - macro chips    │
│    PlanCanvas     (payload available)        │   - input field    │
├──────────────────────────────────────────────┤                    │
│  DataTablePanel (metrics)                    │                    │
└──────────────────────────────────────────────┴────────────────────┘
```

## Directory Map (`frontend/lib/`)

```
lib/
├── main.dart                 ProviderScope + app entry
├── app.dart                  MaterialApp + PlannerDashboard (3-panel Row/Column)
├── core/
│   ├── config.dart           API_BASE_URL (--dart-define), poll interval
│   ├── api_client.dart       Dio wrapper: uploadFile / getJob / sendChat
│   └── theme.dart            Material 3 dark theme
├── models/
│   └── job.dart              Dart mirror of backend schemas — KEEP IN SYNC
├── state/
│   ├── pipeline_provider.dart  upload → poll → ready lifecycle (Notifier)
│   └── chat_provider.dart      chat history + agent calls (Notifier)
└── features/
    ├── workspace/workspace_panel.dart     drop zone ⇄ canvas switcher
    ├── ingestion/file_drop_zone.dart      file_picker + desktop_drop
    ├── ingestion/pipeline_status_bar.dart status line + reset
    ├── canvas/plan_canvas.dart            CustomPainter geometry renderer
    ├── data_view/data_table_panel.dart    metrics DataTable
    └── console/agent_console.dart         chat UI + macro buttons
```

## State Management (Riverpod)

Two `Notifier` providers own all app state; widgets are `ConsumerWidget`s that
`watch` them — no `setState` business logic anywhere.

```mermaid
flowchart LR
    FDZ[FileDropZone] -- processFile(path) --> PP[pipelineProvider]
    PP -- "POST /jobs, then Timer.periodic GET /jobs/id" --> API[ApiClient]
    PP -- PipelineState(job) --> SB[StatusBar] & CV[PlanCanvas] & DT[DataTable]
    AC[AgentConsole] -- send(msg) --> CP[chatProvider]
    CP -- reads job id --> PP
    CP -- "POST /jobs/id/chat" --> API
    CP -- "List<ChatMessage>" --> AC
```

- **`pipelineProvider`** — `PipelineState { job, uploading, error }`.
  `processFile()` uploads, then polls every `AppConfig.pollInterval` (1 s)
  until `ready`/`failed`; the timer is cancelled on dispose and on `reset()`.
- **`chatProvider`** — ordered `List<ChatMessage>` (`role: user|agent`).
  Refuses politely when no job is `ready` yet; guards against double-sends.

## Plan Viewer (`plan_viewer.dart`)

The canvas area is a **Render / Vectors toggle** (SegmentedButton, top-right):

- **Render** (default): the server-side PNG from `GET /jobs/{id}/render` —
  full-fidelity ezdxf output including block symbols the extractor doesn't
  traverse; zoomable via its own `InteractiveViewer`, with a graceful
  fallback message when no render exists (404).
- **Vectors**: the client-side `PlanCanvas` below — the extracted data layer,
  color-classified per layer semantics.

## Canvas Rendering (`plan_canvas.dart`)

`_PlanPainter` draws the raw `shapely`/`ezdxf` output — no backend-rendered
image needed:

- **Zoom & pan (feature 2):** the painter sits inside an `InteractiveViewer`
  (0.1×–25× zoom, unbounded pan); double-tap resets the view via a
  `TransformationController`
- Scales world coordinates into the viewport using `payload.bounds`
  (uniform scale, 24 px margin) and **flips the Y axis** (CAD is Y-up,
  screen is Y-down)
- Strokes polylines/lines as `Path`s, circles via `drawCircle`
- **Semantic layer colors (feature 2):** `layerColor()` classifies real DB
  layer names by keyword — cabling red, EEA/LST blue, Planung green,
  Rückbau orange, Bestand/context grey, sheet furniture dimmed — with a
  stable 6-color fallback for unknown layers (full table in
  FEATURE_2_REPORT.md §2)
- Plan annotations are drawn with `TextPainter` at their insert points

New `Geometry.kind`s from the backend degrade gracefully: anything with ≥ 2
points is stroked as a path.

## Backend Wiring

`core/config.dart`:

```bash
# local backend (default): http://localhost:8000
flutter run -d linux

# any other backend, e.g. Cloud Run:
flutter run -d linux --dart-define=API_BASE_URL=https://rail50hz-backend-xyz.a.run.app
```

The contract lives in `models/job.dart` and is a **hand-written 1:1 mirror**
of `backend/app/models/schemas.py` (wire format: snake_case JSON). When
changing the backend contract, update both — the widget/unit tests and
`flutter analyze` will catch most drift.

## Platforms

```bash
flutter run -d linux      # primary target (spec)
flutter run -d macos
flutter run -d windows
flutter run -d chrome     # web: drag-and-drop works; file paths come from bytes
```

Note for web: `FilePicker` returns bytes instead of a path there — the upload
call in `api_client.dart` needs a `MultipartFile.fromBytes` branch when web
becomes a real target (desktop-first for the POC).

## Extending

- **New panel:** create `features/<name>/`, add it to the `Row`/`Column` in
  `app.dart`, read state from an existing provider or add a new `Notifier`.
- **New quick-action macro:** append the label to `_macros` in
  `agent_console.dart` — it's sent as a plain chat message.
- **Highlight non-compliant geometry:** the report's `Finding.location`
  carries layer names/coordinates; join it against `payload.geometries` in
  `_PlanPainter` and stroke matches in the error color.

## Checks

```bash
cd frontend
flutter analyze     # zero-issue baseline
flutter test        # widget smoke test: three-panel layout renders
```
