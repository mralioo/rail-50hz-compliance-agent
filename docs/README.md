# Rail50Hz.ai — Documentation

| Document | Contents |
| :--- | :--- |
| [PROGRESS_REPORT.md](PROGRESS_REPORT.md) | **Start here for the product view:** full progress report — feature inventory, architecture, agentic system, CAD engine decision, gaps, roadmap |
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design: components, data flow, sequence diagrams, design decisions, scaling path |
| [API.md](API.md) | REST API reference with request/response examples and the full data contract |
| [BACKEND.md](BACKEND.md) | Backend module guide: pipeline stages, extraction rules, agent modes, RAG corpus format, testing |
| [FRONTEND.md](FRONTEND.md) | Flutter app guide: panel layout, state management, backend wiring, multi-platform support |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Local setup, environment variables, DWG converter engines (LibreDWG/ODA), Docker, Cloud Run, Vertex AI mode |
| [DATASET_INGESTION.md](DATASET_INGESTION.md) | DWG dataset processing: converter build, extraction findings, OpenAI summaries, Cognee memory (plan + run results) |
| [LOCAL_SANDBOX_SPEC.md](LOCAL_SANDBOX_SPEC.md) | Saved spec note ("option A"): local-only sandbox blueprint — zoomable InteractiveViewer canvas, 3-color layer scheme |
| [FEATURE_2_REPORT.md](FEATURE_2_REPORT.md) | Feature 2 implementation report: spec→code mapping, semantic layer colors, zoom/pan canvas, test guide |
| [CAD_ENGINE_EVALUATION.md](CAD_ENGINE_EVALUATION.md) | Open CASCADE (OCCT) feasibility study — rejected for 2D DXF/DWG, kept on the 3D roadmap |
| [CAD_MANIPULATION_ENGINE.md](CAD_MANIPULATION_ENGINE.md) | LibreCAD write/automation feasibility (rejected), the real write engine (ezdxf + dxf2dwg), hands-on round-trip findings, roadmap to requirement-driven planning with ground-truth verification |
| [CAD_ENGINE_FRAMEWORK.md](CAD_ENGINE_FRAMEWORK.md) | Modular `cad_engines` framework (ezdxf/LibreDWG/ACadSharp/QCAD behind one interface), the ACadSharp experiment, benchmark matrix, and the new `/jobs/{id}/dwg` read+manipulate+download API (verified end-to-end against a real DWG, cross-read by a second engine) |
| [QCAD_CONNECTOR.md](QCAD_CONNECTOR.md) | QCAD connector: headless `-autostart` automation, license/subprocess reasoning, the DXF-only finding (no DWG — closed-source QCAD Pro only). `read.js`/`write.js` + `QCadEngine` built and registered; unverified locally (no Qt6/root to build `qcadcmd`) |
| [LOCATOR_AGENT.md](LOCATOR_AGENT.md) | Locator agent: "where is X?" chat queries highlighted as boxes on the render canvas — design, API, verified results |
| [ANALYSIS_AGENT.md](ANALYSIS_AGENT.md) | Analysis agent: per-finding overviews, show/hide boxes, click-to-select, on-demand AI descriptions (token-frugal) |
| [UX_AND_MEMORY.md](UX_AND_MEMORY.md) | Search history, Cognee guideline memory + per-agent prompts, Plan Copilot rename, layer filter, quick guide |
| [DRAFTSMAN_AGENT.md](DRAFTSMAN_AGENT.md) | Draftsman agent: click points on the canvas, copilot sketches cable lines as overlays with lengths + rule reminders |
| [CAD_VIEWER_INTEGRATION.md](CAD_VIEWER_INTEGRATION.md) | mlightcad/cad-viewer integration: self-contained interactive HTML export (`GET /jobs/{id}/viewer`), the Engineer's Console (`GET /jobs/{id}/console`) with chat/locate/findings/history/sketch/knowledge-base tabs, locator hits + Draftsman sketches baked in as real highlighted entities (`POST .../viewer/annotate`), DXF-only GPL reasoning (verified clean), bugs found+fixed |
| [design/gleis-os-system-blueprint.html](design/gleis-os-system-blueprint.html) | Co-founder-facing system blueprint: what's built vs. planned per agent, agent-to-agent comms today vs. target (MCP/A2A), RAG-as-guardrail, the unbuilt CAD-manipulation-agent vision, low-level contracts, roadmap. Open directly in a browser. |
| [design/ROADMAP_CHECKLIST.md](design/ROADMAP_CHECKLIST.md) | Actionable checklist derived from the blueprint's roadmap: 5 prioritized items (Orchestrator, A2A, CAD Manipulation Agent, Verification Agent, broaden knowledge base) with concrete first steps |
| [OPENSEARCH_NEO4J_EVALUATION.md](OPENSEARCH_NEO4J_EVALUATION.md) | OpenSearch (vector) vs Neo4j (graph) knowledge-store evaluation: local Docker PoC (`docker-compose.kb.yml`), ingestion of the real regulation corpus into both, a hybrid fusion script, hands-on setup/bug findings, and the design-decision record |
| [WEBAPP.md](WEBAPP.md) | React web shell (OmniDraft · GLEIS OS, `webapp/`): product naming, IA, tech stack, the iframe-embed decision for the Engineer's Console, the full built-vs-Coming-Soon feature matrix, and brand assets |

**New here?** Read [ARCHITECTURE.md](ARCHITECTURE.md) first, then follow the
Quickstart in the [root README](../README.md).
