import { apiGet } from "./client";
import type { KnowledgeBase } from "./types";

export function listKnowledgeBases(): Promise<KnowledgeBase[]> {
  return apiGet<KnowledgeBase[]>("/knowledge-bases");
}
