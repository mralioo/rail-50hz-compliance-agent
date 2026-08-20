import { useQuery } from "@tanstack/react-query";
import { listKnowledgeBases } from "../api/knowledgeBases";

export function useKnowledgeBases() {
  return useQuery({
    queryKey: ["knowledge-bases"],
    queryFn: listKnowledgeBases,
  });
}
