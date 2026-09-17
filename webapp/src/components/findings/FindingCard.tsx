import { Link } from "react-router-dom";
import type { Finding } from "../../api/types";
import { suggestCraftsmanFix } from "../../lib/findingBridge";

const STATUS_STYLES: Record<Finding["status"], string> = {
  compliant: "border-accent/40 bg-accent/10 text-accent",
  non_compliant: "border-danger/40 bg-danger/10 text-danger",
  warning: "border-amber/40 bg-amber/10 text-amber",
};

const REVIEW_STYLES: Record<Finding["review"]["status"], string> = {
  pending: "border-line-light bg-navy-800 text-ink-muted",
  verified: "border-accent/40 bg-accent/10 text-accent",
  flagged: "border-danger/40 bg-danger/10 text-danger",
};

interface FindingCardProps {
  finding: Finding;
  jobId: string;
  onReview: (status: "verified" | "flagged") => void;
  reviewing: boolean;
}

export function FindingCard({ finding, jobId, onReview, reviewing }: FindingCardProps) {
  const suggestion = suggestCraftsmanFix(finding);

  return (
    <div className="rounded-lg border border-line bg-navy-900 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink-primary">{finding.parameter}</p>
          <p className="mt-0.5 text-xs text-ink-secondary">{finding.regulation}</p>
        </div>
        <span
          className={`shrink-0 rounded-full border px-2.5 py-0.5 text-[11px] font-medium capitalize ${STATUS_STYLES[finding.status]}`}
        >
          {finding.status.replace("_", " ")}
        </span>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-3 text-xs">
        <div>
          <p className="text-ink-muted">Actual</p>
          <p className="mt-0.5 font-mono text-ink-primary">{finding.actual}</p>
        </div>
        <div>
          <p className="text-ink-muted">Expected</p>
          <p className="mt-0.5 font-mono text-ink-primary">{finding.expected}</p>
        </div>
      </div>

      {finding.location && (
        <p className="mt-2 text-[11px] text-ink-muted">Location: {finding.location}</p>
      )}
      {finding.suggestion && (
        <p className="mt-2 text-xs leading-relaxed text-ink-secondary">{finding.suggestion}</p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button
          onClick={() => onReview("verified")}
          disabled={reviewing}
          className={`rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors disabled:opacity-40 ${REVIEW_STYLES[finding.review.status]}`}
        >
          {finding.review.status === "verified" ? "✓ Verified" : "Mark verified"}
        </button>
        <button
          onClick={() => onReview("flagged")}
          disabled={reviewing}
          className="rounded-full border border-danger/40 px-2.5 py-1 text-[11px] font-medium text-danger transition-colors hover:bg-danger/10 disabled:opacity-40"
        >
          {finding.review.status === "flagged" ? "⚑ Flagged" : "Flag"}
        </button>
        {finding.review.reviewed_by && (
          <span className="text-[11px] text-ink-muted">by {finding.review.reviewed_by}</span>
        )}
        {suggestion && (
          <Link
            to={`/app/jobs/${jobId}/craftsman`}
            state={{ suggestedOp: suggestion.op, suggestedRadius: suggestion.radius, reason: suggestion.reason }}
            className="ml-auto rounded-full border border-accent/40 bg-accent/10 px-2.5 py-1 text-[11px] font-medium text-accent hover:bg-accent/20"
          >
            Send to Craftsman →
          </Link>
        )}
      </div>
    </div>
  );
}
