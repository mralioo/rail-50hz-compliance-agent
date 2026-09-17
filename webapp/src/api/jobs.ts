import { apiDelete, apiGet, apiPatchJson, apiPostForm, API_V1 } from "./client";
import type { Finding, Job, JobSummary, ReviewStatus } from "./types";

export function listJobs(limit = 50): Promise<JobSummary[]> {
  return apiGet<JobSummary[]>(`/jobs?limit=${limit}`);
}

export function getJob(jobId: string): Promise<Job> {
  return apiGet<Job>(`/jobs/${jobId}`);
}

/** Permanent - removes the job and its whole work_dir (upload, render,
 * manipulated .dwg, viewer caches) server-side. No undo. */
export function deleteJob(jobId: string): Promise<{ ok: boolean }> {
  return apiDelete<{ ok: boolean }>(`/jobs/${jobId}`);
}

export function createJob(file: File): Promise<Job> {
  const form = new FormData();
  form.append("file", file);
  return apiPostForm<Job>("/jobs", form);
}

export function jobRenderUrl(jobId: string): string {
  return `${API_V1}/jobs/${jobId}/render`;
}

export function jobConsoleUrl(jobId: string): string {
  return `${API_V1}/jobs/${jobId}/console`;
}

export function reviewFinding(
  jobId: string,
  index: number,
  status: ReviewStatus,
  note?: string,
  reviewedBy?: string,
): Promise<Finding> {
  return apiPatchJson<Finding>(`/jobs/${jobId}/findings/${index}/review`, {
    status,
    note: note ?? null,
    reviewed_by: reviewedBy ?? null,
  });
}
