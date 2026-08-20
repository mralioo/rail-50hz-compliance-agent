import { useMemo, useState } from "react";
import { NODE_DOCS, type NodeDoc } from "../../content/nodeDocs";

const GROUP_ORDER = ["Pipeline", "Agents", "Coming Soon"];

/** Right-docked node panel, n8n's "add a node" pattern adapted to our dark
 * navy/cyan theme: a search box, collapsible category sections, sourced
 * from content/nodeDocs.ts (NODE_DOCS) — the same real, hands-on-verified
 * node/agent catalogue the old Node Docs page used, now reused here instead
 * of duplicated. Opened either from the top "+ Add node" button (unwired,
 * `connectFromTitle` is null) or from a node's own inline "+" (wired to
 * auto-connect, `connectFromTitle` names the source node so the panel can
 * say so). Added nodes are reference/planning nodes only (no route) except
 * the 4 Console-hosted agents — see JobWorkflow.tsx. */
export function NodePalette({
  open,
  connectFromTitle,
  onAdd,
  onClose,
}: {
  open: boolean;
  connectFromTitle: string | null;
  onAdd: (doc: NodeDoc) => void;
  onClose: () => void;
}) {
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return NODE_DOCS;
    return NODE_DOCS.filter(
      (d) => d.name.toLowerCase().includes(q) || d.desc.toLowerCase().includes(q) || d.group.toLowerCase().includes(q),
    );
  }, [query]);

  if (!open) return null;

  return (
    <>
      <div className="absolute inset-0 z-10" onClick={onClose} />
      <div className="absolute right-0 top-0 z-20 flex h-full w-80 flex-col border-l border-line bg-navy-900 shadow-2xl">
        <div className="shrink-0 border-b border-line p-3.5">
          <div className="flex items-center justify-between">
            <p className="text-sm font-semibold text-ink-primary">Add a node</p>
            <button
              onClick={onClose}
              aria-label="Close"
              className="rounded-md p-1 text-ink-muted hover:bg-navy-800 hover:text-ink-primary"
            >
              ✕
            </button>
          </div>
          {connectFromTitle && (
            <p className="mt-1 truncate text-[11px] text-accent">Connecting from “{connectFromTitle}”</p>
          )}
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search nodes…"
            className="mt-2.5 w-full rounded-md border border-line bg-navy-950 px-2.5 py-1.5 text-xs text-ink-primary placeholder:text-ink-muted"
          />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-2.5">
          {filtered.length === 0 && (
            <p className="px-1.5 py-3 text-center text-xs text-ink-muted">No nodes match “{query}”.</p>
          )}
          {GROUP_ORDER.map((group) => {
            const items = filtered.filter((d) => d.group === group);
            if (items.length === 0) return null;
            return (
              <div key={group} className="mb-3 last:mb-0">
                <p className="px-1.5 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
                  {group}
                </p>
                <div className="space-y-1">
                  {items.map((doc) => (
                    <button
                      key={doc.name}
                      onClick={() => onAdd(doc)}
                      title={doc.desc}
                      className="flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left hover:bg-navy-800"
                    >
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-navy-800 text-[10px] font-bold text-ink-muted">
                        {doc.mono}
                      </span>
                      <span className="min-w-0">
                        <span className="block truncate text-xs font-medium text-ink-primary">{doc.name}</span>
                        <span className="block truncate text-[10.5px] text-ink-muted">{doc.desc}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
