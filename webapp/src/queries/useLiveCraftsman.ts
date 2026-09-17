import { useMutation } from "@tanstack/react-query";
import { startLiveCraftsman, sendLiveCraftsmanOp, stopLiveCraftsman } from "../api/craftsman";
import type { CraftsmanOp } from "../api/types";

export function useStartLiveCraftsman(jobId: string | undefined) {
  return useMutation({
    mutationFn: () => startLiveCraftsman(jobId as string),
  });
}

export function useLiveCraftsmanOp(jobId: string | undefined) {
  return useMutation({
    mutationFn: (ops: CraftsmanOp[]) => sendLiveCraftsmanOp(jobId as string, ops),
  });
}

export function useStopLiveCraftsman(jobId: string | undefined) {
  return useMutation({
    mutationFn: () => stopLiveCraftsman(jobId as string),
  });
}
