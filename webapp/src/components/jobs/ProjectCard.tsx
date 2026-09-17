import { useState } from "react";
import { Link } from "react-router-dom";
import type { JobSummary } from "../../api/types";
import { jobRenderUrl } from "../../api/jobs";
import { formatRelativeTime } from "../../lib/format";
import { useDeleteJob } from "../../queries/useJobs";
import { StatusBadge } from "./StatusBadge";

/** Bigger project-style card (Anvil mockup's "Projects" grid) backed by a
 * real render thumbnail (GET /jobs/{id}/render) instead of a placeholder —
 * falls back to a text placeholder while the plan is still processing or if
 * the render isn't ready yet. */
export function ProjectCard({ job }: { job: JobSummary }) {
  const [thumbFailed, setThumbFailed] = useState(false);
  const showThumb = job.status === "ready" && !thumbFailed;
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
      className="group relative block rounded-xl border border-line bg-navy-900 p-4 shadow-sm transition-all hover:-translate-y-0.5 hover:border-line-light hover:shadow-lg"
    >
      <button
        onClick={handleDelete}
        disabled={deleteJob.isPending}
        title="Delete project"
        aria-label="Delete project"
        className="absolute right-2.5 top-2.5 z-10 hidden h-6 w-6 items-center justify-center rounded-md border border-line-light bg-navy-950/90 text-ink-muted transition-colors hover:border-danger/40 hover:text-danger group-hover:flex disabled:cursor-not-allowed disabled:opacity-40"
      >
        ✕
      </button>
      <div className="mb-3.5 flex h-20 items-center justify-center overflow-hidden rounded-md border border-line bg-navy-950">
        {showThumb ? (
          <img
            src={jobRenderUrl(job.id)}
            alt=""
            className="h-full w-full object-contain"
            onError={() => setThumbFailed(true)}
          />
        ) : (
          <span className="text-[11px] font-semibold tracking-wide text-ink-muted">
            2D CAD PREVIEW
          </span>
        )}
      </div>
      <div className="flex items-start justify-between gap-2">
        <p className="truncate text-sm font-semibold text-ink-primary">{job.filename}</p>
        <StatusBadge status={job.status} />
      </div>
      <p className="mt-0.5 truncate font-mono text-xs text-ink-muted">{job.id}</p>
      {job.created_at && (
        <p className="mt-2.5 text-[11px] text-ink-muted">
          Updated {formatRelativeTime(job.created_at)}
        </p>
      )}
    </Link>
  );
}
