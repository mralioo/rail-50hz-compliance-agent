import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from "@xyflow/react";
import { useCanvasActions } from "./CanvasActionsContext";

export interface PipelineEdgeData extends Record<string, unknown> {
  /** Shown in a hover tooltip at the edge midpoint — what flows along this
   * connection. Falls back to a generic "source → target" label for
   * freeform user-drawn edges, which have no canned description. */
  description?: string;
}

/** n8n-style connector: same bezier path React Flow draws by default, plus
 * a CSS-hover-revealed label and a "✕" delete button at the midpoint. Used
 * via the `edgeTypes` prop alongside `nodeTypes` on the Main Workspace
 * canvas (JobWorkflow.tsx). */
export function PipelineFlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
  style,
}: EdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    targetX,
    targetY,
    sourcePosition,
    targetPosition,
  });
  const d = data as PipelineEdgeData | undefined;
  const label = d?.description ?? "Connection";
  const { deleteEdge } = useCanvasActions();

  return (
    <>
      <BaseEdge id={id} path={edgePath} markerEnd={markerEnd} style={style} />
      <EdgeLabelRenderer>
        <div
          className="group pointer-events-auto absolute"
          style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
        >
          <button
            onClick={(e) => {
              e.stopPropagation();
              deleteEdge(id);
            }}
            title="Delete connection"
            aria-label="Delete connection"
            className="flex h-4 w-4 items-center justify-center rounded-full border-2 border-navy-950 bg-line-light text-[8px] font-bold text-navy-950 opacity-0 transition-all hover:bg-danger hover:text-white group-hover:opacity-100"
          >
            ✕
          </button>
          <div className="pointer-events-none absolute left-1/2 top-1/2 z-10 hidden w-52 -translate-x-1/2 -translate-y-[calc(100%+10px)] rounded-md border border-line bg-navy-900 px-2.5 py-1.5 text-[11px] leading-snug text-ink-secondary shadow-lg group-hover:block">
            {label}
          </div>
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
