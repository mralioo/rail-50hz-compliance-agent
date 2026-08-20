import { Link } from "react-router-dom";
import type { JobStatus } from "../../api/types";
import { StatusBadge } from "../jobs/StatusBadge";

interface TopbarProps {
  jobId: string;
  filename: string;
  status: JobStatus;
}

/** Job-specific chrome: back link + filename + status + share link. No tab
 * strip — the Main Workspace canvas (JobWorkflow) is the sole per-job hub;
 * every other job-scoped screen (Sources/Findings/Craftsman/Console) is
 * reached by clicking its node on that canvas, not a top-level tab. The
 * back arrow returns to the Main Workspace canvas (not the dashboard) so a
 * node-click drill-down always has a one-click way back to the hub. */
export function Topbar({ jobId, filename, status }: TopbarProps) {
  return (
    <div className="border-b border-line bg-navy-900">
      <div className="flex items-center gap-3 px-4 py-2.5">
        <Link
          to={`/app/jobs/${jobId}/workflow`}
          className="text-ink-secondary transition-colors hover:text-ink-primary"
          aria-label="Back to Main Workspace"
        >
          ←
        </Link>
        <span className="truncate text-sm font-medium text-ink-primary">{filename}</span>
        <StatusBadge status={status} />
        <button
          onClick={() => navigator.clipboard.writeText(window.location.href)}
          className="ml-auto shrink-0 rounded-md border border-line-light px-2.5 py-1 text-[11.5px] font-medium text-ink-secondary transition-colors hover:border-accent/40 hover:text-ink-primary"
          title="Copy a shareable link to this project"
        >
          Copy link ↗
        </button>
      </div>
    </div>
  );
}
