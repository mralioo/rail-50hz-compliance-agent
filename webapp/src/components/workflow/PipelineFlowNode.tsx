import { Handle, Position, type NodeProps } from "@xyflow/react";
import type { JobStatus } from "../../api/types";
import { useCanvasActions } from "./CanvasActionsContext";

export type NodeState = "done" | "active" | "pending" | "failed" | "disabled";

export interface PipelineNodeData extends Record<string, unknown> {
  mono: string;
  title: string;
  subtitle: string;
  state: NodeState;
  badge?: string;
  clickable?: boolean;
  /** Shown in a hover tooltip — what this node actually does. */
  description?: string;
  /** Route suffix appended to /app/jobs/:id, if this node opens a real page. */
  to?: string;
  /** Drives live state sync against the job's JobStatus — omit for freeform
   * palette-added/reference nodes, which keep whatever state they were
   * created with. */
  stage?: JobStatus;
  /** Always "done" once the job exists (e.g. Upload) — never re-synced. */
  alwaysDone?: boolean;
}

const STATE_STYLES: Record<NodeState, string> = {
  done: "bg-accent/10 border-accent/40",
  active: "bg-accent/10 border-accent animate-pulse",
  pending: "bg-navy-800 border-line-light",
  failed: "bg-danger/10 border-danger/40",
  disabled: "bg-navy-900 border-line opacity-60",
};

const MARK_STYLES: Record<NodeState, string> = {
  done: "bg-accent text-navy-950",
  active: "bg-accent text-navy-950",
  pending: "bg-navy-700 text-ink-muted",
  failed: "bg-danger text-white",
  disabled: "bg-navy-800 text-ink-muted",
};

const handleClass = "!h-2.5 !w-2.5 !border-2 !border-navy-950 !bg-line-light";

/** n8n-style node: draggable, connectable via the left/right handles, click
 * (not drag) navigates to the node's real page when it has one. Hovering
 * reveals a description tooltip and two affordances borrowed straight from
 * n8n: a "✕" to delete the node (top-right corner) and a "+" past the
 * output handle that opens the palette pre-wired to auto-connect whatever
 * gets picked next. Used on the Main Workspace canvas (JobWorkflow.tsx) via
 * React Flow's nodeTypes. */
export function PipelineFlowNode({ id, data, selected }: NodeProps) {
  const d = data as PipelineNodeData;
  const { addNodeFrom, deleteNode } = useCanvasActions();

  return (
    <div className="group relative">
      <button
        onClick={(e) => {
          e.stopPropagation();
          deleteNode(id);
        }}
        title="Delete node"
        aria-label="Delete node"
        className="absolute -right-2 -top-2 z-10 hidden h-5 w-5 items-center justify-center rounded-full border border-line-light bg-navy-950 text-[10px] text-ink-muted transition-colors hover:border-danger/40 hover:text-danger group-hover:flex"
      >
        ✕
      </button>
      <div
        className={`w-[160px] rounded-xl border p-3 shadow-sm transition-shadow ${STATE_STYLES[d.state]} ${
          selected ? "ring-2 ring-accent" : ""
        } ${d.clickable ? "cursor-pointer" : ""}`}
      >
        <Handle type="target" position={Position.Left} className={handleClass} />
        <div className="flex items-center justify-between">
          <div
            className={`flex h-6 w-6 items-center justify-center rounded-md text-[10px] font-bold ${MARK_STYLES[d.state]}`}
          >
            {d.mono}
          </div>
          {d.badge && (
            <span className="rounded-full border border-amber/40 bg-amber/10 px-1.5 py-0.5 text-[9px] font-medium text-amber">
              {d.badge}
            </span>
          )}
        </div>
        <p className="mt-2 text-[12.5px] font-semibold text-ink-primary">{d.title}</p>
        <p className="mt-0.5 text-[10.5px] leading-tight text-ink-secondary">{d.subtitle}</p>
        <Handle type="source" position={Position.Right} className={handleClass} />
      </div>
      <button
        onClick={(e) => {
          e.stopPropagation();
          addNodeFrom(id);
        }}
        title="Add a connected node"
        aria-label="Add a connected node"
        className="absolute -right-6 top-1/2 z-10 hidden h-5 w-5 -translate-y-1/2 items-center justify-center rounded-full border border-line-light bg-navy-950 text-[11px] font-semibold text-ink-muted transition-colors hover:border-accent/60 hover:text-accent group-hover:flex"
      >
        +
      </button>
      {d.description && (
        <div className="pointer-events-none absolute -top-2 left-1/2 z-10 hidden w-56 -translate-x-1/2 -translate-y-full rounded-md border border-line bg-navy-900 px-2.5 py-1.5 text-[11px] leading-snug text-ink-secondary shadow-lg group-hover:block">
          {d.description}
        </div>
      )}
    </div>
  );
}
