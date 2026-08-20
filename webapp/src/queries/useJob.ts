import { useQuery } from "@tanstack/react-query";
import { getJob } from "../api/jobs";
import { TERMINAL_JOB_STATUSES, type Job } from "../api/types";

export function useJob(jobId: string | undefined) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => getJob(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const job = query.state.data as Job | undefined;
      if (!job) return 2000;
      return TERMINAL_JOB_STATUSES.includes(job.status) ? false : 2000;
    },
  });
}
