import { apiPostJson, API_V1 } from "./client";
import type { CraftsmanOp, CraftsmanResponse } from "./types";

export function runCraftsman(
  jobId: string,
  ops: CraftsmanOp[],
  dwgVersion = "r2018",
): Promise<CraftsmanResponse> {
  return apiPostJson<CraftsmanResponse>(`/jobs/${jobId}/craftsman`, {
    ops,
    dwg_version: dwgVersion,
  });
}

/** Same interactive cad-viewer as jobViewerUrl, rendering the Craftsman
 * agent's latest result - only valid after runCraftsman has been called at
 * least once for this job (see GET /jobs/{id}/craftsman/viewer). */
export function craftsmanViewerUrl(jobId: string): string {
  return `${API_V1}/jobs/${jobId}/craftsman/viewer`;
}

export interface CraftsmanLiveStartResponse {
  html_url: string;
}

/** Starts a real, persistent FreeCAD GUI session for this job, streamed
 * into the browser via xpra's HTML5 client (`html_url` - embed it in an
 * iframe). One global session at a time (see backend/app/craftsman/
 * live_bridge.py) - starting a new job's session tears down any other
 * job's first. May reject with a 502 if FREECAD_GUI_PATH/XPRA_PATH aren't
 * configured - see docs/CRAFTSMAN_AGENT.md. */
export function startLiveCraftsman(jobId: string): Promise<CraftsmanLiveStartResponse> {
  return apiPostJson<CraftsmanLiveStartResponse>(`/jobs/${jobId}/craftsman/live/start`, {});
}

/** Sends ops to the running live session - same request/response shape as
 * runCraftsman, different transport (a persistent FreeCAD document instead
 * of a fresh one-shot subprocess), so $prev now persists across calls for
 * the whole live session, not just within one call. */
export function sendLiveCraftsmanOp(
  jobId: string,
  ops: CraftsmanOp[],
  dwgVersion = "r2018",
): Promise<CraftsmanResponse> {
  return apiPostJson<CraftsmanResponse>(`/jobs/${jobId}/craftsman/live/op`, {
    ops,
    dwg_version: dwgVersion,
  });
}

export function stopLiveCraftsman(jobId: string): Promise<{ ok: boolean }> {
  return apiPostJson<{ ok: boolean }>(`/jobs/${jobId}/craftsman/live/stop`, {});
}
