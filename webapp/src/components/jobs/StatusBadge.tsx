import type { JobStatus } from "../../api/types";

const STATUS_STYLES: Record<JobStatus, string> = {
  queued: "border-amber/40 bg-amber/10 text-amber",
  converting: "border-amber/40 bg-amber/10 text-amber",
  extracting: "border-amber/40 bg-amber/10 text-amber",
  analyzing: "border-amber/40 bg-amber/10 text-amber",
  ready: "border-accent/40 bg-accent/10 text-accent",
  failed: "border-danger/40 bg-danger/10 text-danger",
};

const PENDING_STATUSES: readonly JobStatus[] = [
  "queued",
  "converting",
  "extracting",
  "analyzing",
];

export function StatusBadge({ status }: { status: JobStatus }) {
  const pulsing = PENDING_STATUSES.includes(status);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium capitalize ${STATUS_STYLES[status]}`}
    >
      <span className={`h-1.5 w-1.5 rounded-full bg-current ${pulsing ? "animate-pulse" : ""}`} />
      {status}
    </span>
  );
}
