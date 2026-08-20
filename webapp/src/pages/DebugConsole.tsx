import { useState } from "react";
import { AppShell } from "../components/layout/AppShell";
import { useDebugSession, useDebugRequests, useDebugCommands, useDebugXpraLog } from "../queries/useDebug";
import { useStopLiveCraftsman } from "../queries/useLiveCraftsman";

type Tab = "traffic" | "commands" | "xpra-log";

/** HH:MM:SS - precise, not relative, since this is a debug tool where exact
 * ordering/timing of recent events matters more than "just now" would. */
function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString("en-GB");
}

function StatusDot({ ok }: { ok: boolean }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-accent" : "bg-danger"}`} />;
}

function statusColor(status: number): string {
  if (status >= 500) return "text-danger";
  if (status >= 400) return "text-amber";
  return "text-accent";
}

/** Debug Console: everything needed to watch, debug, and fix the backend
 * while it's running - the live FreeCAD session's real health (not just
 * "does an object exist"), every HTTP request hitting the backend, every
 * Craftsman op (headless or live) with its real result, and a tail of the
 * xpra log a live session writes to. In-memory only (backend/app/core/
 * debug_log.py) - resets on backend restart, same durability as the rest
 * of this POC. Polls every 2s while open. See docs/CRAFTSMAN_AGENT.md. */
export function DebugConsole() {
  const [tab, setTab] = useState<Tab>("traffic");
  const { data: sessionData } = useDebugSession();
  const { data: requests } = useDebugRequests();
  const { data: commands } = useDebugCommands();
  const session = sessionData?.session ?? null;
  const xpraLog = useDebugXpraLog(tab === "xpra-log");
  const stopLive = useStopLiveCraftsman(session?.job_id);

  return (
    <AppShell>
      <div className="flex h-full flex-col px-6 py-4">
        <div className="shrink-0">
          <h1 className="text-base font-semibold text-ink-primary">Debug Console</h1>
          <p className="mt-0.5 text-xs text-ink-secondary">
            Live FreeCAD session health, request traffic, and every Craftsman command — auto-refreshes every 2s.
          </p>
        </div>

        {/* Live session card */}
        <div className="mt-4 shrink-0 rounded-xl border border-line bg-navy-900 p-3.5">
          <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
            Live FreeCAD session
          </p>
          {!session ? (
            <p className="text-xs text-ink-muted">No live session running.</p>
          ) : (
            <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
              <span className="flex items-center gap-1.5 text-ink-primary">
                <StatusDot ok={session.process_alive} />
                {session.process_alive ? "Running" : "Process exited"}
              </span>
              <span className="text-ink-secondary">
                Job <span className="font-mono text-ink-primary">{session.job_id}</span>
              </span>
              <span className="text-ink-secondary">
                PID <span className="font-mono text-ink-primary">{session.pid}</span>
              </span>
              <span className="text-ink-secondary">
                Uptime <span className="text-ink-primary">{Math.round(session.uptime_s)}s</span>
              </span>
              <span className="flex items-center gap-1.5 text-ink-secondary">
                <StatusDot ok={session.op_port_open} />
                Op port {session.op_port}
              </span>
              <span className="flex items-center gap-1.5 text-ink-secondary">
                <StatusDot ok={session.html_ready} />
                HTML port {session.html_port}
              </span>
              <a
                href={session.html_url}
                target="_blank"
                rel="noreferrer"
                className="text-accent hover:underline"
              >
                Open viewer ↗
              </a>
              <button
                onClick={() => stopLive.mutate()}
                disabled={stopLive.isPending}
                className="ml-auto rounded-md border border-danger/40 px-2.5 py-1 text-[11px] font-semibold text-danger hover:bg-danger/10 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {stopLive.isPending ? "Stopping…" : "Stop session"}
              </button>
            </div>
          )}
        </div>

        {/* Tabs */}
        <div className="mt-4 flex shrink-0 gap-1 border-b border-line">
          {(
            [
              ["traffic", "Traffic"],
              ["commands", "Commands"],
              ["xpra-log", "xpra log"],
            ] as [Tab, string][]
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`px-3 py-2 text-xs font-semibold ${
                tab === id ? "border-b-2 border-accent text-ink-primary" : "text-ink-muted hover:text-ink-secondary"
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        <div className="mt-3 min-h-0 flex-1 overflow-auto rounded-xl border border-line bg-navy-900">
          {tab === "traffic" && (
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-navy-900">
                <tr className="border-b border-line text-[10px] uppercase tracking-wider text-ink-muted">
                  <th className="px-3 py-2 font-semibold">Time</th>
                  <th className="px-3 py-2 font-semibold">Method</th>
                  <th className="px-3 py-2 font-semibold">Path</th>
                  <th className="px-3 py-2 font-semibold">Status</th>
                  <th className="px-3 py-2 font-semibold">Duration</th>
                </tr>
              </thead>
              <tbody>
                {(requests ?? []).map((r, i) => (
                  <tr key={i} className="border-b border-line/50">
                    <td className="whitespace-nowrap px-3 py-1.5 text-ink-muted">{formatTime(r.ts)}</td>
                    <td className="px-3 py-1.5 font-mono text-ink-secondary">{r.method}</td>
                    <td className="max-w-[420px] truncate px-3 py-1.5 font-mono text-ink-primary">{r.path}</td>
                    <td className={`px-3 py-1.5 font-mono font-semibold ${statusColor(r.status)}`}>{r.status}</td>
                    <td className="px-3 py-1.5 text-ink-muted">{r.duration_ms.toFixed(0)}ms</td>
                  </tr>
                ))}
                {(requests ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-ink-muted">
                      No requests recorded yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}

          {tab === "commands" && (
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-navy-900">
                <tr className="border-b border-line text-[10px] uppercase tracking-wider text-ink-muted">
                  <th className="px-3 py-2 font-semibold">Time</th>
                  <th className="px-3 py-2 font-semibold">Job</th>
                  <th className="px-3 py-2 font-semibold">Transport</th>
                  <th className="px-3 py-2 font-semibold">Op</th>
                  <th className="px-3 py-2 font-semibold">Result</th>
                </tr>
              </thead>
              <tbody>
                {(commands ?? []).map((c, i) => (
                  <tr key={i} className="border-b border-line/50 align-top">
                    <td className="whitespace-nowrap px-3 py-1.5 text-ink-muted">{formatTime(c.ts)}</td>
                    <td className="px-3 py-1.5 font-mono text-ink-secondary">{c.job_id}</td>
                    <td className="px-3 py-1.5">
                      <span
                        className={`rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${
                          c.transport === "live"
                            ? "border-accent/40 bg-accent/10 text-accent"
                            : "border-line-light text-ink-muted"
                        }`}
                      >
                        {c.transport}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 font-mono text-ink-primary">{c.op}</td>
                    <td className={`px-3 py-1.5 ${c.ok ? "text-ink-secondary" : "text-danger"}`}>{c.detail}</td>
                  </tr>
                ))}
                {(commands ?? []).length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-3 py-6 text-center text-ink-muted">
                      No Craftsman commands run yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}

          {tab === "xpra-log" && (
            <div className="p-3 font-mono text-[11px] leading-relaxed text-ink-secondary">
              {xpraLog.data?.lines.length ? (
                xpraLog.data.lines.map((line, i) => (
                  <div key={i} className="whitespace-pre-wrap">
                    {line}
                  </div>
                ))
              ) : (
                <p className="text-ink-muted">No xpra log yet — starts once a live session has run.</p>
              )}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  );
}
