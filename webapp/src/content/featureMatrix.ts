export interface FeatureMatrixItem {
  title: string;
  description: string;
  tone: "built" | "coming-soon" | "partial";
  roadmapSlug?: string;
}

/**
 * The single place every capability — built or not — is represented
 * honestly on the marketing landing page. Built items link to real
 * in-app pages; Coming Soon items link to /app/roadmap/{slug} (zero
 * network calls, see src/content/roadmap.ts).
 */
export const FEATURE_MATRIX: FeatureMatrixItem[] = [
  {
    title: "DWG/DXF ingestion pipeline",
    description:
      "Upload a real plan, watch it move through convert → extract → analyze → ready, backed by ezdxf + shapely geometry extraction.",
    tone: "built",
  },
  {
    title: "5 built compliance agents",
    description:
      "Compliance Analyst, Plan Copilot, Locator, Analyzer, and Draftsman — all live inside every processed job's Workspace.",
    tone: "built",
  },
  {
    title: "Interactive CAD viewer",
    description:
      "Pan, zoom, measure, and filter by layer on a self-contained interactive export of the uploaded plan.",
    tone: "built",
  },
  {
    title: "Regulation knowledge base",
    description:
      "Ril / VDE regulation corpus, organized by knowledge base, grounding both chat and structured findings.",
    tone: "built",
  },
  {
    title: "Search history",
    description: "Every Locator query is saved and re-runnable across sessions.",
    tone: "built",
  },
  {
    title: "Formal Orchestrator",
    description: "A real reasoning agent to route requests, replacing today's client-side regex router.",
    tone: "coming-soon",
    roadmapSlug: "orchestrator",
  },
  {
    title: "Agent-to-Agent protocol",
    description: "A peer interface between agents, replacing today's in-process function calls.",
    tone: "coming-soon",
    roadmapSlug: "a2a",
  },
  {
    title: "CAD Manipulation Agent",
    description: "Natural-language instruction → drafted DWG edits, reviewed before write-back.",
    tone: "coming-soon",
    roadmapSlug: "cad-manipulation-agent",
  },
  {
    title: "Verification Agent",
    description: "A pre-write guardrail checking proposed edits against the knowledge base and clearances.",
    tone: "coming-soon",
    roadmapSlug: "verification-agent",
  },
  {
    title: "Semantic & graph knowledge store",
    description: "OpenSearch + Neo4j retrieval, evaluated but not yet wired into production.",
    tone: "coming-soon",
    roadmapSlug: "semantic-kb",
  },
  {
    title: "Sketch export to DXF",
    description: "Persisting Draftsman's sketch overlays back into the source file.",
    tone: "coming-soon",
    roadmapSlug: "sketch-export",
  },
  {
    title: "Block reference extraction",
    description: "Reading INSERT/ATTRIB block content — the highest-value known extraction gap.",
    tone: "coming-soon",
    roadmapSlug: "block-extraction",
  },
  {
    title: "Firm system integrations",
    description: "SharePoint, Autodesk Construction Cloud, Procore connectors.",
    tone: "coming-soon",
    roadmapSlug: "integrations",
  },
];
