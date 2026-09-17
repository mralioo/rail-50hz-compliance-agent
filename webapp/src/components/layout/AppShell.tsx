import type { ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { useHealth } from "../../queries/useHealth";

function HealthPill() {
  const { data, isError } = useHealth();

  if (isError) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-danger/40 bg-danger/10 px-2.5 py-1 text-xs text-danger">
        <span className="h-1.5 w-1.5 rounded-full bg-danger" />
        Backend unreachable
      </span>
    );
  }

  if (!data) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-line-light px-2.5 py-1 text-xs text-ink-muted">
        Checking backend…
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-accent/40 bg-accent/10 px-2.5 py-1 text-xs text-accent">
      <span className="h-1.5 w-1.5 rounded-full bg-accent" />
      agent_mode: {data.agent_mode}
    </span>
  );
}

/** Shell for every /app/* route: fixed sidebar + scrollable content area. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen bg-navy-950">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-line px-6 py-3">
          <span className="text-xs uppercase tracking-widest text-ink-muted">
            OmniDraft · GLEIS OS demo workspace
          </span>
          <HealthPill />
        </header>
        <main className="min-h-0 flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
