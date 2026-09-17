import { createContext, useContext } from "react";

export interface CanvasActions {
  /** Opens the node palette pre-wired to auto-connect the new node from
   * this node's output — the n8n "+" -after-a-node pattern. */
  addNodeFrom: (nodeId: string) => void;
  deleteNode: (nodeId: string) => void;
  deleteEdge: (edgeId: string) => void;
}

/** Lets PipelineFlowNode/PipelineFlowEdge trigger add/delete without the
 * callbacks living in React Flow's own `data` (which gets JSON-persisted
 * to localStorage on every change — functions can't round-trip through
 * that, so they're kept out of it entirely and supplied via context
 * instead). Provided once by JobWorkflow's CanvasInner. */
const CanvasActionsContext = createContext<CanvasActions | null>(null);

export const CanvasActionsProvider = CanvasActionsContext.Provider;

export function useCanvasActions(): CanvasActions {
  const ctx = useContext(CanvasActionsContext);
  if (!ctx) throw new Error("useCanvasActions must be used within CanvasActionsProvider");
  return ctx;
}
