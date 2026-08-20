import { apiPostJson } from "./client";
import type { ChatResponse } from "./types";

/** Plan Copilot - RAG-grounded chat scoped to this job's plan + regulation
 * knowledge bases. Backs the "Ask about parts" tab on the Node Runtime page
 * (see docs/UI/anvil-platform-ui-mockups' Node Runtime chat panel). */
export function sendChat(jobId: string, message: string): Promise<ChatResponse> {
  return apiPostJson<ChatResponse>(`/jobs/${jobId}/chat`, { message });
}
