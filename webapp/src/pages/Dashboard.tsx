import { AppShell } from "../components/layout/AppShell";
import { UploadDropzone } from "../components/jobs/UploadDropzone";
import { ProjectCard } from "../components/jobs/ProjectCard";
import { useJobs } from "../queries/useJobs";
import { TERMINAL_JOB_STATUSES } from "../api/types";

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line bg-navy-900 px-5 py-4">
      <p className="text-2xl font-semibold text-ink-primary">{value}</p>
      <p className="mt-1 text-xs text-ink-muted">{label}</p>
    </div>
  );
}

export function Dashboard() {
  const { data: jobs, isLoading, isError } = useJobs();

  const total = jobs?.length ?? 0;
  const ready = jobs?.filter((j) => j.status === "ready").length ?? 0;
  const failed = jobs?.filter((j) => j.status === "failed").length ?? 0;
  const inProgress = jobs?.filter((j) => !TERMINAL_JOB_STATUSES.includes(j.status)).length ?? 0;

  return (
    <AppShell>
      <div className="mx-auto max-w-6xl px-6 py-10">
        <p className="text-xs font-medium uppercase tracking-widest text-ink-muted">Workspace</p>
        <h1 className="mt-1 text-xl font-semibold text-ink-primary">Select a project</h1>
        <p className="mt-1 text-sm text-ink-secondary">
          Upload a plan to run it through extraction, compliance, and the Craftsman agent — or
          open an existing project below.
        </p>

        <div className="mt-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Total projects" value={total} />
          <StatCard label="Ready" value={ready} />
          <StatCard label="In progress" value={inProgress} />
          <StatCard label="Failed" value={failed} />
        </div>

        <div className="mt-8 max-w-xl">
          <UploadDropzone />
        </div>

        <div className="mt-10">
          <h2 className="text-sm font-medium uppercase tracking-wider text-ink-muted">
            Recent projects
          </h2>
          {isLoading && <p className="mt-3 text-sm text-ink-muted">Loading projects…</p>}
          {isError && (
            <p className="mt-3 text-sm text-danger">
              Couldn't reach the backend. Is it running (`make backend`)?
            </p>
          )}
          {jobs?.length === 0 && (
            <p className="mt-3 text-sm text-ink-muted">No projects yet — upload a plan above.</p>
          )}
          <div className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {jobs?.map((job) => <ProjectCard key={job.id} job={job} />)}
          </div>
        </div>
      </div>
    </AppShell>
  );
}
