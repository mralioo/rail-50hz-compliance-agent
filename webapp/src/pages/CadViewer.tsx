import { AppShell } from "../components/layout/AppShell";
import { UploadDropzone } from "../components/jobs/UploadDropzone";
import { JobCard } from "../components/jobs/JobCard";
import { useJobs } from "../queries/useJobs";

/**
 * The web-app equivalent of `make viewer`: a persistent, always-in-nav
 * entry point into the interactive DWG viewer + chat, instead of it only
 * being reachable by first clicking into a job from the Dashboard.
 * Picking or uploading a plan here hands off to a job's Main Workspace,
 * which routes to the real Engineer's Console (viewer + Plan Copilot chat)
 * via the Console node.
 */
export function CadViewer() {
  const { data: jobs, isLoading, isError } = useJobs();
  const readyJobs = jobs?.filter((j) => j.status === "ready") ?? [];
  const otherJobs = jobs?.filter((j) => j.status !== "ready") ?? [];

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl px-6 py-10">
        <h1 className="text-xl font-semibold text-ink-primary">DWG Viewer</h1>
        <p className="mt-1 text-sm text-ink-secondary">
          The same interactive pan/zoom/measure DWG viewer and chat behind{" "}
          <code className="rounded bg-navy-900 px-1 py-0.5 font-mono text-xs">make viewer</code>{" "}
          — open a recent plan or upload a new one.
        </p>

        <div className="mt-6">
          <UploadDropzone />
        </div>

        {isLoading && <p className="mt-6 text-sm text-ink-muted">Loading plans…</p>}
        {isError && (
          <p className="mt-6 text-sm text-danger">
            Couldn't reach the backend. Is it running (`make backend`)?
          </p>
        )}

        {readyJobs.length > 0 && (
          <div className="mt-10">
            <h2 className="text-sm font-medium uppercase tracking-wider text-ink-muted">
              Open a recent plan
            </h2>
            <div className="mt-3 space-y-2">
              {readyJobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          </div>
        )}

        {otherJobs.length > 0 && (
          <div className="mt-10">
            <h2 className="text-sm font-medium uppercase tracking-wider text-ink-muted">
              Still processing
            </h2>
            <div className="mt-3 space-y-2">
              {otherJobs.map((job) => (
                <JobCard key={job.id} job={job} />
              ))}
            </div>
          </div>
        )}

        {!isLoading && jobs?.length === 0 && (
          <p className="mt-10 text-sm text-ink-muted">
            No plans uploaded yet — drop a .dwg or .dxf above to open the viewer.
          </p>
        )}
      </div>
    </AppShell>
  );
}
