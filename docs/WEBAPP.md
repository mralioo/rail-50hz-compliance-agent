# OmniDraft · GLEIS OS — React web shell

**Verdict (2026-08-03):** Built and verified end-to-end against the real
backend. A new `webapp/` React app gives the existing agents, CAD engine, and
knowledge base a real product identity — a marketing landing page plus a
sidebar-nav app shell (Dashboard, Workspace, Knowledge Base, Agents,
Settings) — instead of raw API routes and the Flutter desktop app being the
only entry points. Everything wired up is real (upload → pipeline → job
list → the actual Engineer's Console); everything not yet built is a
clearly labeled Coming Soon page that makes no API calls. Verified in a real
browser against a running `make backend`, uploading `sample_plan.dxf`
through to a `ready` job and an interactive Workspace.

## 1. Naming

- **OmniDraft** — the general/umbrella platform brand. Broad "AI drafting &
  compliance platform for AEC firms" framing, with room to grow beyond rail
  into other AEC verticals.
- **GLEIS OS** — the vertical module built this iteration: 50Hz railway
  electrical planning/compliance, running on the Rail50Hz.ai backend.
- Shown nested everywhere as **"OmniDraft · GLEIS OS"** (eyebrow text,
  lockup wordmark) — the same pattern as "Notion · Notion Calendar": one
  platform, one named module inside it.

## 2. Information architecture

```
/                          marketing landing (OmniDraft · GLEIS OS)
/app                       redirect → /app/dashboard
/app/dashboard             Dashboard — job list + upload + stats        [REAL]
/app/jobs/:jobId           Workspace — topbar + iframe embed            [REAL]
/app/knowledge-base        Knowledge Base list                         [REAL]
/app/agents                Agents roster (static)                      [REAL]
/app/settings              Settings (agent_mode real, rest Coming Soon) [PARTIAL]
/app/roadmap/:slug         generic Coming Soon page (content-driven)   [STATIC]
```

No auth — the app goes straight into a single "Demo Workspace" (no login
form, since the backend has no auth to back one).

## 3. Tech stack

- **Vite + React 18 + TypeScript** — `webapp/` is a sibling to `backend/`
  and `frontend/` (the Flutter app; `frontend/` stays as-is, this is a
  second, web-only client).
- **Tailwind CSS v4** (`@tailwindcss/vite` plugin, CSS-based `@theme`
  config in `src/styles/globals.css` — no separate `tailwind.config.ts`
  needed in v4).
- **React Router v6** — two route trees, marketing (`/`) and app shell
  (`/app/*`).
- **`@tanstack/react-query`** for data fetching, chosen specifically for job
  status polling: `queued → converting → extracting → analyzing →
  ready/failed`. `useQuery({ refetchInterval: (q) => isTerminal(status) ?
  false : 2000 })` handles interval refetch with automatic stop-on-terminal
  cleanly (see `src/queries/useJob.ts`, `useJobs.ts`) — a hand-rolled
  `setInterval` would need the same logic plus manual cleanup. The upload
  mutation also gets a free `invalidateQueries(['jobs'])` for the dashboard
  list. No Redux/Zustand — the query cache plus local component state covers
  this app's whole surface area.
- **Vite pinned to v6.4.3**, not the newer v8 line: this environment's Node
  (v22.11.0) is just under the v22.12.0 floor Vite 8's bundled `rolldown`
  native bindings require, and `npm install` silently produced a broken
  binding (`Cannot find native binding` at build time). Vite 6 uses the
  mature esbuild/rollup toolchain with no such native-binding resolution
  issue on this Node version. Verified: `npm run build` completes cleanly
  (123 modules, no TS errors) on 6.4.3.

## 4. Why the console is embedded, not reimplemented

The full agent toolset — chat, Locator, Findings, History, Sketch,
Knowledge Base filter, and the interactive pan/zoom/measure CAD viewer —
already exists, fully working, as a self-contained HTML page:
`GET /api/v1/jobs/{id}/console`, rendered by
`render_console_shell()` in `backend/app/viewer/__init__.py` from
`backend/app/viewer/assets/console_shell.html`. This was already built and
verified in prior work (see `docs/CAD_VIEWER_INTEGRATION.md`).

Rather than re-deriving that entire stack as native React components (chat
state, Locator hit rendering, sketch click-capture, the cad-viewer
integration itself), the Workspace page (`src/pages/Workspace.tsx`) embeds
it directly:

```tsx
<iframe src={jobConsoleUrl(job.id)} className="min-h-0 flex-1 border-0" />
```

**No CORS exposure, regardless of the React app's own origin**: the
console's own JavaScript makes relative fetches (`/api/v1/jobs/{id}/...`)
resolved against *the iframe's own document origin* — i.e. the backend,
since the backend is what served that HTML document. Those calls never
cross an origin boundary and never touch the backend's `cors_origins`
setting. The React app's *own* direct calls (jobs list/upload, knowledge
bases, health) do cross origins if the app isn't served from the same host
as the backend, which is why `cors_origins = ["*"]` in
`backend/app/core/config.py` matters for *those* calls — but not for
anything inside the iframe.

Verified live (2026-08-03): uploaded `backend/data/samples/sample_plan.dxf`
via the Dashboard, watched it reach `ready`, opened its Workspace — the
iframe loaded the real interactive viewer with the sample's actual
`E_CABLE`/`E_ROOM` geometry and annotations (`NYY-J 5x16 / R=90`, `max pull:
620 N`, `Schaltraum UV 50Hz`, `acc. to Ril 954.0107`) rendered correctly,
chat/findings/history/sketch/knowledge-base tabs all present and
interactive.

## 5. Built vs. Coming Soon — feature matrix

| Feature | Status | Backend endpoint(s) |
|---|---|---|
| DWG/DXF ingestion pipeline | **Built** | `POST /jobs`, `GET /jobs/{id}` |
| Job dashboard + stats | **Built** | `GET /jobs` |
| Workspace (embedded Engineer's Console) | **Built** | `GET /jobs/{id}/console` |
| Compliance Analyst, Plan Copilot, Locator, Analyzer, Draftsman | **Built** (inside the console) | `/chat`, `/locate`, `/hits/analyze`, `/hits/describe`, `/draw` |
| Knowledge Steward (regulation RAG) | **Built** | `GET /knowledge-bases` |
| Search history | **Built** (inside the console) | `GET /searches` |
| Agent mode display | **Built** | `GET /health` |
| Formal Orchestrator | Coming Soon | — (today: client-side regex router in `console_shell.html`) |
| Agent-to-Agent (A2A) protocol | Coming Soon | — (0 agent-to-agent messages today, all in-process calls) |
| CAD Manipulation Agent | Coming Soon | low-level `POST /jobs/{id}/dwg/manipulate` exists; no NL-driven agent |
| Verification Agent | Coming Soon | — |
| Semantic & graph knowledge store (OpenSearch/Neo4j) | Coming Soon | eval-only, not wired to any endpoint — see `docs/OPENSEARCH_NEO4J_EVALUATION.md` |
| Sketch export to DXF | Coming Soon | — (session-only overlay today) |
| Block reference (INSERT/ATTRIB) extraction | Coming Soon | — (highest-value known extraction gap) |
| Firm system integrations (SharePoint/ACC/Procore) | Coming Soon | — (no connector code) |
| Team accounts & SSO | Coming Soon | — (no auth at all today) |

Every Coming Soon item is content-driven from `src/content/roadmap.ts` and
rendered by `src/components/shared/ComingSoon.tsx`, which makes zero API
calls. Verified via the browser's network panel on `/app/roadmap/semantic-kb`
— the only request that fired was the shared app-shell health pill's
`GET /api/v1/health`, nothing roadmap-specific.

## 6. Branding assets

Extends the mark already embedded in `GLEIS-OS Pitch (standalone).html`
(a cyan chevron/rail-switch silhouette with cyan+amber crossbars and a cyan
apex node on navy) rather than inventing a new one.

- **Mark concept**: two converging rail lines forming a chevron (a track
  switch/frog in plan view), apex capped by a filled circle — a "signal
  node" reading as a rail signal, a circuit node, and an agent-network node
  at once. Two horizontal crossbars = rail sleepers, doubling as an
  abstracted waveform. Cyan `#29E0FF` carries the primary structure; amber
  `#F5B23D` is reserved for the base crossbar only, matching the app's
  sparing secondary-accent rule.
- Files: `webapp/public/brand/omnidraft-mark.svg` (square mark),
  `webapp/public/brand/omnidraft-lockup.svg` (mark + two-tier wordmark:
  "OMNIDRAFT" over smaller monospace cyan "GLEIS OS"),
  `webapp/public/favicon.svg` (mark on a rounded navy square).
- Rendered via `src/components/shared/Logo.tsx`.

Unified color tokens (`webapp/src/styles/globals.css`, Tailwind v4
`@theme`) fold the pitch-deck palette (navy `#0A0E1A`, cyan `#29E0FF`,
amber `#F5B23D`) and the console's own dark tokens (`#0b0d10`/`#12151a`
backgrounds, `#262b33`/`#2e3540` borders, `#dfe4ea`/`#8a92a1`/`#6b7383`
text, `#e0463a` error) into one set — the console's separate `#4ea1ff`
accent is folded into the app's single `#29E0FF` accent so the embedded
iframe reads as part of the same product, not a bolted-on tool.

## 7. Running it

```
make webapp-install   # cd webapp && npm install
make webapp           # cd webapp && npm run dev  (http://localhost:5173)
```

Requires the backend running separately (`make backend`,
`http://localhost:8000` by default — override via `webapp/.env.local`'s
`VITE_API_BASE_URL`).
