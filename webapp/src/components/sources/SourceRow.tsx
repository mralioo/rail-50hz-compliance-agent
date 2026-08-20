interface SourceRowProps {
  mono: string;
  name: string;
  desc: string;
  connected?: boolean;
  comingSoon?: boolean;
  docHref?: string;
}

/** One row in the Connect Sources list — mirrors the Anvil mockup's source
 * row layout, but only ever shows real, live data sources as "Connected";
 * anything not actually wired up (Neo4j, vector store, SharePoint, PLM)
 * renders disabled and labeled Coming Soon rather than faked. */
export function SourceRow({ mono, name, desc, connected, comingSoon, docHref }: SourceRowProps) {
  return (
    <div className="flex items-center gap-3.5 border-b border-line px-4 py-3 last:border-b-0">
      <div
        className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[11px] font-semibold ${
          comingSoon ? "bg-navy-800 text-ink-muted" : "bg-accent/10 text-accent"
        }`}
      >
        {mono}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-ink-primary">{name}</p>
        <p className="truncate text-xs text-ink-secondary">{desc}</p>
      </div>
      {comingSoon ? (
        docHref ? (
          <a
            href={docHref}
            target="_blank"
            rel="noreferrer"
            className="shrink-0 rounded-full border border-amber/40 bg-amber/10 px-2.5 py-1 text-[11px] font-medium text-amber hover:underline"
          >
            Coming Soon ↗
          </a>
        ) : (
          <span className="shrink-0 rounded-full border border-amber/40 bg-amber/10 px-2.5 py-1 text-[11px] font-medium text-amber">
            Coming Soon
          </span>
        )
      ) : (
        <span className="shrink-0 rounded-full border border-accent/40 bg-accent/10 px-2.5 py-1 text-[11px] font-medium text-accent">
          {connected ? "Connected" : "Not connected"}
        </span>
      )}
    </div>
  );
}
