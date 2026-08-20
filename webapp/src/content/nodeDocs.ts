export interface NodeDoc {
  mono: string;
  name: string;
  group: string;
  desc: string;
  input: string;
  output: string;
}

/**
 * Reference cards for every real node on the workflow canvas and every real
 * agent — sourced from the actual backend contract (backend/app/api/routes.py,
 * docs/CRAFTSMAN_AGENT.md), not the Anvil mockup's fictional Docling/generic
 * connector nodes. Static content, same pattern as content/agents.ts, so the
 * docs page and the canvas never drift from what's actually implemented.
 */
export const NODE_DOCS: NodeDoc[] = [
  {
    mono: "▲",
    name: "Upload",
    group: "Pipeline",
    desc: "Engineer uploads a .dwg or .dxf plan, creating a job.",
    input: "multipart file",
    output: "{job_id, status: queued}",
  },
  {
    mono: "CV",
    name: "Convert",
    group: "Pipeline",
    desc: "DWG → DXF via LibreDWG's dwg2dxf (DXF uploads pass through untouched).",
    input: "{file_path}",
    output: "{dxf_path}",
  },
  {
    mono: "EX",
    name: "Extract",
    group: "Pipeline",
    desc: "Parses layers, geometry (line/polyline/circle), and text/annotations out of the DXF.",
    input: "{dxf_path}",
    output: "{layers[], geometries[], texts[], metrics[]}",
  },
  {
    mono: "CA",
    name: "Compliance Analyst",
    group: "Agents",
    desc: "Checks extracted metrics/annotations against Ril / VDE regulation limits (bending radius, pulling force, citation currency).",
    input: "{payload, regulation corpus}",
    output: "{findings[] (compliant | non_compliant | warning), summary}",
  },
  {
    mono: "PC",
    name: "Plan Copilot",
    group: "Agents",
    desc: "Conversational, regulation-grounded chat scoped to the job's own findings and payload.",
    input: "{message, job_id}",
    output: "{reply}",
  },
  {
    mono: "LO",
    name: "Locator",
    group: "Agents",
    desc: 'Resolves a natural-language query (e.g. "where is the Schalthaus?") to highlighted bounding boxes on the plan.',
    input: "{query, job_id}",
    output: "{hits[] (bbox, layer, text)}",
  },
  {
    mono: "AN",
    name: "Analyzer",
    group: "Agents",
    desc: "Deterministic region stats for a Locator hit, with an opt-in AI description.",
    input: "{hit, job_id}",
    output: "{stats, description?}",
  },
  {
    mono: "DR",
    name: "Draftsman",
    group: "Agents",
    desc: "Connects planner-clicked points into a labeled sketch overlay with real-world length + rule reminders.",
    input: "{instruction, points_image[]}",
    output: "{element, reply}",
  },
  {
    mono: "KS",
    name: "Knowledge Steward",
    group: "Agents",
    desc: "Non-persona: parses machine-readable limit blocks out of the regulation corpus, backing both Compliance Analyst and Plan Copilot.",
    input: "regulation markdown corpus",
    output: "{rules, knowledge_bases[]}",
  },
  {
    mono: "CR",
    name: "Craftsman Agent",
    group: "Agents",
    desc: "Real 2D geometry ops (offset/fillet/join wires) via headless FreeCAD; writes a real .dwg back out.",
    input: "{ops[] (upgrade_objects | offset_wire | fillet_wire), job_id}",
    output: "{geometries[], texts[], layers[], op_results[], warnings[], download_url}",
  },
  {
    mono: "KB",
    name: "Knowledge Base",
    group: "Pipeline",
    desc: "Connects this job's selected knowledge bases (regulation corpora) as grounding context for Craftsman and Plan Copilot. Manage which KBs are active on the Data Sources page.",
    input: "{knowledge_base_ids[]}",
    output: "grounding context for Craftsman / Plan Copilot",
  },
  {
    mono: "GR",
    name: "Graph DB Writer",
    group: "Coming Soon",
    desc: "Entity/relation graph writes for structural queries — evaluation PoC only, not wired into any live endpoint.",
    input: "{entities[], relations[]}",
    output: "{node_ids[], edge_ids[]}",
  },
  {
    mono: "VC",
    name: "Vector DB Writer",
    group: "Coming Soon",
    desc: "Embeddings for semantic retrieval — evaluation PoC only, current retrieval is keyword-match.",
    input: "{chunks[]}",
    output: "{vector_ids[]}",
  },
];
