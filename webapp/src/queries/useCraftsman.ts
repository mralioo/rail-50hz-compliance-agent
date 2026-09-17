import { useMutation } from "@tanstack/react-query";
import { runCraftsman } from "../api/craftsman";
import type { CraftsmanOp } from "../api/types";

export function useCraftsman(jobId: string | undefined) {
  return useMutation({
    mutationFn: (ops: CraftsmanOp[]) => runCraftsman(jobId as string, ops),
  });
}
