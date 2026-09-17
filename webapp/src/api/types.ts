/**
 * Mirrors backend/app/models/schemas.py exactly. Keep in sync when the
 * backend contract changes — the same convention that file already asks of
 * frontend/lib/models/ (the Flutter client).
 */

export type JobStatus =
  | "queued"
  | "converting"
  | "extracting"
  | "analyzing"
  | "ready"
  | "failed";

export const TERMINAL_JOB_STATUSES: readonly JobStatus[] = ["ready", "failed"];

export interface Geometry {
  layer: string;
  kind: string; // "polyline" | "line" | "circle"
  points: [number, number][];
  closed: boolean;
  radius: number | null;
}

export interface TextItem {
  layer: string;
  text: string;
  position: [number, number];
}

export interface Metric {
  name: string;
  value: number;
  unit: string;
  layer: string | null;
}

export interface DataLayerPayload {
  source_file: string;
  layers: string[];
  geometries: Geometry[];
  texts: TextItem[];
  metrics: Metric[];
  bounds: [number, number, number, number] | null;
}

export type FindingStatus = "compliant" | "non_compliant" | "warning";

/** Engineer verify/flag state on a finding - separate from the agent's own
 * FindingStatus judgement. See PATCH /jobs/{id}/findings/{index}/review. */
export type ReviewStatus = "pending" | "verified" | "flagged";

export interface FindingReview {
  status: ReviewStatus;
  note: string | null;
  reviewed_by: string | null;
}

export interface Finding {
  status: FindingStatus;
  parameter: string;
  actual: string;
  expected: string;
  regulation: string;
  location: string | null;
  suggestion: string | null;
  review: FindingReview;
}

export interface ComplianceReport {
  findings: Finding[];
  summary: string;
}

export interface Job {
  id: string;
  status: JobStatus;
  filename: string;
  error: string | null;
  payload: DataLayerPayload | null;
  report: ComplianceReport | null;
  created_at: string;
}

/** Lightweight Job listing entry — no payload/report, safe to list many. */
export interface JobSummary {
  id: string;
  filename: string;
  status: JobStatus;
  created_at: string;
}

/** Real 2D geometry ops (offset/fillet/join) via the FreeCAD-backed
 * Craftsman agent - see docs/CRAFTSMAN_AGENT.md. Distinct from the flat
 * add/remove DwgEditOp used by /dwg/manipulate.
 *
 * `id`/`ids` may be "$prev" - the object the previous op in the SAME
 * `ops` array created. Only works within one call (each POST /craftsman
 * re-reads the original upload from scratch), which is exactly why a
 * multi-step SOP must be sent as one call with every step in `ops`, not as
 * separate sequential calls - see content/sops.ts. */
export interface CraftsmanOp {
  op: string; // "upgrade_objects" | "offset_wire" | "fillet_wire"
  ids?: string[] | null; // upgrade_objects
  id?: string | null; // offset_wire / fillet_wire
  delta?: number[] | null; // offset_wire: [dx, dy, (dz)] in mm
  radius?: number | null; // fillet_wire: corner radius in mm
  edge_indices?: number[] | null; // fillet_wire: the 2 adjacent edges to round
}

export interface CraftsmanObject {
  id: string;
  kind: "geometry" | "text";
  layer: string;
}

export interface CraftsmanOpResult {
  op: string;
  ok: boolean;
  detail: string;
}

export interface CraftsmanResponse {
  layers: string[];
  geometries: Geometry[];
  texts: TextItem[];
  objects: CraftsmanObject[];
  op_results: CraftsmanOpResult[];
  warnings: string[];
  download_url: string;
}

export interface ChatRequest {
  message: string;
  knowledge_bases?: string[] | null;
}

export interface ChatResponse {
  reply: string;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  doc_count: number;
}

export type AgentMode = "mock" | "openai" | "vertex";

export interface HealthResponse {
  status: string;
  agent_mode: AgentMode;
}
