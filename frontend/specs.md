```markdown
# FLUTTER_PLAYGROUND_SPEC.md

## Project Overview & Goal
The objective is to construct a Flutter Linux desktop application that serves as an interactive "Planner's Playground." This workspace will mimic an electrical planner's desktop environment and serve as the frontend sandbox to test, visualize, and refine the integration of our Agentic AI system and classical automation workflows. 

The application must allow users to upload a raw `DWG` file, trigger the cloud-based processing pipeline, and interact with the AI Agent regarding the extracted design elements.

---

## Tech Stack & Dependencies

### Frontend Framework
*   **Flutter Desktop (Linux)**

### Core Packages (`pubspec.yaml`)
*   `file_picker`: For native Linux file system dialogs to select `DWG` files.
*   `dio` or `http`: For handling multi-part form uploads and REST communication with the backend.
*   `flutter_riverpod` or `provider`: For clean state management of agent conversations and pipeline states.
*   `canvas` / `CustomPainter`: For rendering geometric shape data returned by the data layer.

---

## UI Layout Architecture (Planner Dashboard)

The interface should be divided into a three-panel workstation layout to maximize scannability and ease of use:

### 1. Ingestion & Visual Canvas (Left/Center Panel)
*   **File Drop Zone:** A clean, dashed-border drop area supporting click-to-pick or drag-and-drop functionality specifically filtered for `.dwg` extensions.
*   **Pipeline Status Indicator:** A state-driven progress bar tracking the lifecycle of the file: *Idle → Uploading → Converting (DWG to DXF) → Extracting Geometry → Ready*.
*   **Playground Canvas:** A viewport that displays either the visual render (PNG/SVG) returned by the backend or dynamically paints the polygon coordinates (`shapely` outputs) using Flutter's `CustomPainter`.

### 2. Structured Data Layer View (Bottom Panel)
*   A data table or clean tree-view showing the processed metadata extracted from the layers (e.g., Calculated Room Areas, Cabling Runs, Wall Lengths).

### 3. Agentic Interactive Console (Right Panel)
*   A chat-style interface dedicated to interacting with the AI Agent.
*   Quick-action macro buttons for common planning inquiries (e.g., *"Verify VDE Compliance"*, *"Check Bending Radii"*, *"Generate Explanatory Report"*).

---

## Core Logic & Backend Connector

The Linux app acts as an orchestrator for the backend pipeline. The system flow must follow this asynchronous sequence:

```text
[Flutter UI: Select DWG] 
         │
         ▼ (HTTP POST Multi-part)
[GCP Cloud Run / Local FastAPI Dev Gateway]
         │
         ▼ (Triggers ODA Converter & ezdxf/shapely Extraction)
[Data Layer Payload Returned]
         │
         ├──► Visual Render (PNG/SVG) ──► Render on Flutter Canvas
         └──► Structured Metadata ────► Populate Data Table & Hydrate Agent Context

```

### API Connector Interface Requirements

* **`POST /api/v1/ingest`**: Sends the raw binary `DWG` file. Must return a tracking ID and the initial ingestion status.
* **`GET /api/v1/status/{id}`**: Polls or listens to WebSockets for pipeline completion metrics.
* **`GET /api/v1/artifacts/{id}`**: Fetches the structured JSON payload (geometric data) and the asset URL for the visual blueprint layout.
* **`POST /api/v1/agent/query`**: Sends user strings or macro commands along with the artifact context to get streaming text responses from the AI validation agent.

---

## Step-by-Step Implementation Prompts for AI Coding Agent

### Phase 1: Environment & File Ingestion

> "Create a new Flutter Linux desktop project structure. Implement a clean, modern dark-themed layout with a three-panel grid system. In the main panel, implement a file selection zone using the `file_picker` package that restricts selection to `.dwg` files. Display the chosen file path, file size, and an 'Upload to Pipeline' action button."

### Phase 2: HTTP Networking Client

> "Implement an API service class using `Dio` to upload the selected file via a multi-part form request to a configurable base URL. Include robust error handling for network timeouts or invalid file formats. Create a state machine class to manage the pipeline states: idle, uploading, processing, success, and failure."

### Phase 3: Canvas Rendering & Agent Console

> "Design a `CustomPainter` widget that parses a mockup JSON containing polygon coordinates and labels, rendering them as scalable lines and shapes in the viewport. On the right side panel, implement a scrollable chat UI for the AI agent workspace, complete with an input text field and a list of predefined action chips that automatically send text macros."

```

---

To ensure the layout aligns perfectly with your workflow, what specific electrical planning components or metrics (such as circuit counts, cable tray routes, or cabinet dimensions) should have dedicated shortcuts or readouts on the main dashboard panel?

```