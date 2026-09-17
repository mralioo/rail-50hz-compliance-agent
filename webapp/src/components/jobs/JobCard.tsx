import { Link } from "react-router-dom";
import type { JobSummary } from "../../api/types";
import { useDeleteJob } from "../../queries/useJobs";
import { StatusBadge } from "./StatusBadge";

export function JobCard({ job }: { job: JobSummary }) {
  const deleteJob = useDeleteJob();

  function handleDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (window.confirm(`Delete "${job.filename}"? This removes the upload and every generated file — no undo.`)) {
      deleteJob.mutate(job.id);
    }
  }

  return (
    <Link
      to={`/app/jobs/${job.id}/workflow`}
      className="group flex items-center justify-between gap-4 rounded-lg border border-line bg-navy-900 px-4 py-3 transition-colors hover:border-line-light hover:bg-navy-800"
    >
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-ink-primary">{job.filename}</p>
        <p className="mt-0.5 truncate text-xs text-ink-muted">{job.id}</p>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <StatusBadge status={job.status} />
        <button
          onClick={handleDelete}
          disabled={deleteJob.isPending}
          title="Delete project"
          aria-label="Delete project"
          className="hidden h-6 w-6 items-center justify-center rounded-md border border-line-light text-ink-muted transition-colors hover:border-danger/40 hover:text-danger group-hover:flex disabled:cursor-not-allowed disabled:opacity-40"
        >
          ✕
        </button>
      </div>
    </Link>
  );
}
