import { useParams } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { Topbar } from "../components/layout/Topbar";
import { FindingCard } from "../components/findings/FindingCard";
import { useJob } from "../queries/useJob";
import { useReviewFinding } from "../queries/useReviewFinding";

/** SOP & Steps, mapped onto what's real: the Compliance Analyst's findings
 * for this plan (Ril/VDE), with a real verify/flag trail (§2 backend
 * addition) instead of the mockup's generic manufacturing steps. Findings
 * with a fixable geometry issue bridge straight into the Craftsman agent. */
export function JobFindings() {
  const { jobId } = useParams<{ jobId: string }>();
  const { data: job, isLoading } = useJob(jobId);
  const review = useReviewFinding(jobId);

  const findings = job?.report?.findings ?? [];

  return (
    <AppShell>
      <div className="flex h-full flex-col">
        {job && <Topbar jobId={job.id} filename={job.filename} status={job.status} />}
        <div className="min-h-0 flex-1 overflow-auto px-6 py-10">
          <div className="mx-auto max-w-3xl">
            <p className="text-xs font-medium uppercase tracking-widest text-ink-muted">
              {job?.filename}
            </p>
            <h1 className="mt-1 text-xl font-semibold text-ink-primary">
              Compliance findings &amp; verification
            </h1>
            <p className="mt-1 max-w-xl text-sm text-ink-secondary">
              Every finding the Compliance Analyst raised against Ril / VDE regulations. Verify or
              flag each before treating this plan as reviewed — findings with a fixable geometry
              issue can be sent straight to the Craftsman agent.
            </p>

            {job?.report?.summary && (
              <div className="mt-5 rounded-lg border border-line bg-navy-900 px-4 py-3 text-sm text-ink-secondary">
                {job.report.summary}
              </div>
            )}

            <div className="mt-6 space-y-3">
              {isLoading && <p className="text-sm text-ink-muted">Loading…</p>}
              {job && !job.report && (
                <p className="text-sm text-ink-muted">
                  No compliance report yet — this plan is still processing.
                </p>
              )}
              {job?.report && findings.length === 0 && (
                <p className="text-sm text-ink-muted">No findings — plan is fully compliant.</p>
              )}
              {findings.map((finding, index) => (
                <FindingCard
                  key={index}
                  finding={finding}
                  jobId={jobId as string}
                  reviewing={review.isPending}
                  onReview={(status) => review.mutate({ index, status, reviewedBy: "You" })}
                />
              ))}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
