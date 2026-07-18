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