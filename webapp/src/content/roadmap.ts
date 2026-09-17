export interface RoadmapEntry {
  slug: string;
  title: string;
  eyebrow: string;
  description: string;
  statusNote: string;
  docLink?: { href: string; label: string };
}

/**
 * Every item here is explicitly NOT wired to any backend endpoint — the
 * RoadmapPage that renders these makes zero network requests. Sourced from
 * docs/design/ROADMAP_CHECKLIST.md and docs/PROGRESS_REPORT.md's gap list.
 */
export const ROADMAP_ENTRIES: RoadmapEntry[] = [
  {
    slug: "orchestrator",
    title: "Formal Orchestrator",
    eyebrow: "Agent roster",
    description:
      "A real server-side coordinating agent that routes a planner's request to the right tool. Today, routing is a client-side regex router inside the Engineer's Console chat box — not a reasoning agent.",
    statusNote: "Partial — regex router exists, no reasoning agent yet",
  },
  {
    slug: "a2a",
    title: "Agent-to-Agent (A2A) Protocol",
    eyebrow: "Agent roster",
    description:
      "A peer interface letting the Compliance Analyst, Locator, Analyzer, Draftsman, and Knowledge Steward call each other directly, instead of every call being routed in-process by the FastAPI layer.",
    statusNote: "Not started — 0 agent-to-agent messages exist today",
  },
  {
    slug: "cad-manipulation-agent",
    title: "CAD Manipulation Agent",
    eyebrow: "Agent roster",
    description:
      "Real 2D geometry ops (offset/fillet/join wires) via a FreeCAD-backed engine, run against the originally uploaded DWG/DXF and written back as a real .dwg. Live today as the Craftsman node in every job's Main Workspace canvas — natural-language instruction parsing on top of the ops API is still on the roadmap.",
    statusNote: "Live — open any job's Main Workspace and click the Craftsman node. NL instruction layer not started yet.",
    docLink: {
      href: "https://github.com/mralioo/rail-50hz-compliance-agent/blob/main/docs/CRAFTSMAN_AGENT.md",
      label: "Read docs/CRAFTSMAN_AGENT.md",
    },
  },
  {
    slug: "verification-agent",
    title: "Verification Agent",
    eyebrow: "Agent roster",
    description:
      "A pre-write guardrail that re-checks any proposed edit or finding against the knowledge base and geometric clearances before it's applied — the last check before a CAD Manipulation Agent would be allowed to write.",
    statusNote: "Not started",
  },
  {
    slug: "semantic-kb",
    title: "Semantic & Graph Knowledge Store",
    eyebrow: "Knowledge base",
    description:
      "OpenSearch (vector/semantic retrieval) and Neo4j (explicit citation/supersession relationships) as a replacement for the regulation corpus's current keyword-match retrieval.",
    statusNote:
      "Evaluation PoC only — a working Docker Compose stack and ingestion scripts exist, but neither store is wired into any live endpoint (feature-flagged off by default).",
    docLink: {
      href: "https://github.com/mralioo/rail-50hz-compliance-agent/blob/main/docs/OPENSEARCH_NEO4J_EVALUATION.md",
      label: "Read the evaluation doc",
    },
  },
  {
    slug: "sketch-export",
    title: "Sketch Persistence & DXF Export",
    eyebrow: "Draftsman",
    description:
      "Writing Draftsman's clicked-and-sketched cable-line overlays back into the DXF file, so a sketch survives beyond the current session.",
    statusNote: "Not started — sketches are session-only overlays today",
  },
  {
    slug: "block-extraction",
    title: "Block Reference (INSERT/ATTRIB) Extraction",
    eyebrow: "Extraction pipeline",
    description:
      "Reading block-reference geometry and attributes, not just top-level entities. Flagged as the highest-value extraction gap — it's why some real-world DWG files parse with zero text entities today.",
    statusNote: "Not started",
  },
  {
    slug: "integrations",
    title: "Firm System Integrations",
    eyebrow: "Platform",
    description:
      "Connectors into the systems firms already use for project files and communication — SharePoint, Autodesk Construction Cloud, Procore.",
    statusNote: "Not started — no connector code exists yet",
  },
];

export function getRoadmapEntry(slug: string | undefined): RoadmapEntry | undefined {
  return ROADMAP_ENTRIES.find((entry) => entry.slug === slug);
}
