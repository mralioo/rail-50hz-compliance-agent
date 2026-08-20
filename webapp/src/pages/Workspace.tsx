import { Link, useParams } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { Topbar } from "../components/layout/Topbar";
import { JobStatusStepper } from "../components/jobs/JobStatusStepper";
import { useJob } from "../queries/useJob";
import { jobConsoleUrl } from "../api/jobs";

export function Workspace() {
  const { jobId } = useParams<{ jobId: string }>();
  const { data: job, isLoading, isError } = useJob(jobId);

  return (
    <AppShell>
      <div className="flex h-full flex-col">
        {job && <Topbar jobId={job.id} filename={job.filename} status={job.status} />}

        {isLoading && !job && (
          <div className="flex flex-1 items-center justify-center text-sm text-ink-muted">
            Loading job…
          </div>
        )}

        {isError && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
            <p className="text-sm text-danger">Job not found.</p>
            <Link to="/app/dashboard" className="text-sm text-accent hover:underline">
              ← Back to dashboard
            </Link>
          </div>
        )}

        {job?.status === "failed" && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 text-center">
            <p className="text-sm text-danger">Processing failed.</p>
            {job.error && <p className="max-w-md text-xs text-ink-muted">{job.error}</p>}
            <Link to="/app/dashboard" className="text-sm text-accent hover:underline">
              ← Back to dashboard, try another upload
            </Link>
          </div>
        )}

        {job && job.status !== "failed" && job.status !== "ready" && (
          <JobStatusStepper status={job.status} />
        )}

        {job?.status === "ready" && (
          <iframe
            title="GLEIS OS Engineer's Console"
            src={jobConsoleUrl(job.id)}
            className="min-h-0 flex-1 border-0"
          />
        )}
      </div>
    </AppShell>
  );
}
