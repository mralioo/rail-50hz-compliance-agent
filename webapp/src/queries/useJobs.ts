import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createJob, deleteJob, listJobs } from "../api/jobs";
import { TERMINAL_JOB_STATUSES, type JobSummary } from "../api/types";

const JOBS_KEY = ["jobs"] as const;

export function useJobs(limit = 50) {
  return useQuery({
    queryKey: JOBS_KEY,
    queryFn: () => listJobs(limit),
    refetchInterval: (query) => {
      const jobs = query.state.data as JobSummary[] | undefined;
      const anyPending = jobs?.some((j) => !TERMINAL_JOB_STATUSES.includes(j.status));
      return anyPending ? 2000 : false;
    },
  });
}

export function useCreateJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => createJob(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: JOBS_KEY });
    },
  });
}

export function useDeleteJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => deleteJob(jobId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: JOBS_KEY });
    },
  });
}
