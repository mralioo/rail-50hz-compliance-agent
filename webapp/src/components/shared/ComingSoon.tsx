import { Link } from "react-router-dom";
import type { RoadmapEntry } from "../../content/roadmap";
import { BadgePill } from "./BadgePill";

/** Pure static content — makes zero API calls. */
export function ComingSoon({ entry }: { entry: RoadmapEntry }) {
  return (
    <div className="mx-auto max-w-2xl px-6 py-16">
      <p className="text-xs font-medium uppercase tracking-widest text-ink-muted">
        {entry.eyebrow}
      </p>
      <div className="mt-2 flex items-center gap-3">
        <h1 className="text-2xl font-semibold text-ink-primary">{entry.title}</h1>
        <BadgePill tone="coming-soon" />
      </div>
      <p className="mt-4 text-sm leading-relaxed text-ink-secondary">{entry.description}</p>

      <div className="mt-6 rounded-lg border border-line bg-navy-900 px-4 py-3 text-xs text-ink-muted">
        {entry.statusNote}
      </div>

      <div className="mt-8 flex items-center gap-4 text-sm">
        <Link to="/app/dashboard" className="text-accent hover:underline">
          ← Back to dashboard
        </Link>
        {entry.docLink && (
          <a
            href={entry.docLink.href}
            target="_blank"
            rel="noreferrer"
            className="text-ink-secondary hover:text-ink-primary hover:underline"
          >
            {entry.docLink.label} ↗
          </a>
        )}
      </div>
    </div>
  );
}
