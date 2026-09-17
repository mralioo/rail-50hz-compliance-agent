import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reviewFinding } from "../api/jobs";
import type { ReviewStatus } from "../api/types";

export function useReviewFinding(jobId: string | undefined) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      index,
      status,
      note,
      reviewedBy,
    }: {
      index: number;
      status: ReviewStatus;
      note?: string;
      reviewedBy?: string;
    }) => reviewFinding(jobId as string, index, status, note, reviewedBy),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["job", jobId] });
    },
  });
}
