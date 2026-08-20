export interface AgentEntry {
  name: string;
  role: string;
  capabilities: string[];
  persona: boolean;
}

/**
 * The 5 built agent personas + the Knowledge Steward (non-persona, the RAG
 * corpus backing chat grounding and the Knowledge Base page). All of these
 * live inside the embedded Engineer's Console (Workspace page) — this page
 * is a static roster, not a separate UI for them.
 */
export const BUILT_AGENTS: AgentEntry[] = [
  {
    name: "Compliance Analyst",
    role: "Structured findings against Ril / VDE regulations",
    capabilities: [
      "Runs on every processed job — bending radius, pulling force, and other Ril 954.9101 / VDE 0100-520 limits",
      "3 selectable backends: mock (deterministic, offline), OpenAI, Vertex (Gemini)",
      "Produces the compliant / non-compliant / warning findings shown in the console's Findings tab",
    ],
    persona: true,
  },
  {
    name: "Plan Copilot",
    role: "Conversational, regulation-grounded chat",
    capabilities: [
      "Answers planner questions grounded in the job's own findings and payload",
      "Retrieves supporting regulation text via the Knowledge Steward's RAG corpus",
      "Filterable per knowledge base (general / db / vde) from the console's Knowledge Base tab",
    ],
    persona: true,
  },
  {
    name: "Locator",
    role: "Visual grounding of natural-language queries",
    capabilities: [
      'Resolves a query like "where is the Schalthaus?" to highlighted bounding boxes on the plan',
      "LLM term-expansion when an API key is configured, keyword/stopword matching otherwise",
      "Every search is saved to history, browsable and re-runnable from the console's History tab",
    ],
    persona: true,
  },
  {
    name: "Analyzer",
    role: "Per-hit deep dive, free by default",
    capabilities: [
      "Deterministic region stats (entity counts, layers present, annotations) for every Locator hit — no LLM, no cost",
      "Opt-in AI description, generated only when a planner clicks \"Describe\", to keep token spend user-controlled",
    ],
    persona: true,
  },
  {
    name: "Draftsman",
    role: "Click-to-sketch cable-line overlays",
    capabilities: [
      "Planner clicks two points on the plan; Draftsman connects them into a labeled sketch overlay",
      "Computes real-world length and reminds the planner of the relevant bending-radius / pulling-force rule",
      "Sketches are session-only today — DXF write-back is on the roadmap",
    ],
    persona: true,
  },
  {
    name: "Knowledge Steward",
    role: "Regulation corpus + retrieval (non-persona)",
    capabilities: [
      "Parses machine-readable limit blocks out of the regulation markdown corpus (general / db / vde)",
      "Backs both the Compliance Analyst's deterministic checks and Plan Copilot's chat grounding",
      "Today: keyword-match retrieval — see the Semantic Knowledge Store roadmap item for the vector/graph upgrade path",
    ],
    persona: false,
  },
  {
    name: "Craftsman",
    role: "Real 2D geometry edits via a FreeCAD-backed engine",
    capabilities: [
      "Offsets a wire or rounds a corner (fillet) on the originally uploaded plan, run through headless FreeCAD",
      "Writes a real .dwg back out — not a sketch overlay — via the same DWG engine the rest of the pipeline trusts (ACadSharp)",
      "Has its own Node Runtime page with a live interactive CAD viewer — see docs/CRAFTSMAN_AGENT.md",
    ],
    persona: true,
  },
];
