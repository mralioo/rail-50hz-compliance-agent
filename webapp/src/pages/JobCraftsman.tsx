import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import { AppShell } from "../components/layout/AppShell";
import { Topbar } from "../components/layout/Topbar";
import { useJob } from "../queries/useJob";
import { useCraftsman } from "../queries/useCraftsman";
import { useStartLiveCraftsman, useLiveCraftsmanOp, useStopLiveCraftsman } from "../queries/useLiveCraftsman";
import { useChat } from "../queries/useChat";
import { craftsmanViewerUrl } from "../api/craftsman";
import { API_BASE_URL } from "../api/client";
import { SOPS } from "../content/sops";
import type { CraftsmanOp, CraftsmanOpResult, CraftsmanResponse } from "../api/types";

interface LoggedAction {
  op: CraftsmanOp;
  result: CraftsmanOpResult;
  step?: string;
}

function opToFreecadLine(op: CraftsmanOp): string {
  if (op.op === "offset_wire") {
    const [dx = 0, dy = 0, dz = 0] = op.delta ?? [];
    return `Draft.offset(doc.getObject(${JSON.stringify(op.id)}), Vector(${dx}, ${dy}, ${dz}), copy=True)`;
  }
  if (op.op === "fillet_wire") {
    const [i = 0, j = 1] = op.edge_indices ?? [];
    return `Draft.make_fillet([doc.getObject(${JSON.stringify(op.id)}).Shape.Edges[${i}], .Edges[${j}]], radius=${op.radius})`;
  }
  if (op.op === "upgrade_objects") {
    return `Draft.upgrade([${(op.ids ?? []).map((id) => JSON.stringify(id)).join(", ")}], delete=True)`;
  }
  return `# ${op.op}`;
}

type Tab = "chat" | "console";
type StepStatus = "pending" | "running" | "done" | "failed";

interface ChatMessage {
  role: "user" | "agent";
  text: string;
}

/** Job-scoped Node Runtime: the Craftsman agent's real FreeCAD execution
 * surface - full-page 3-pane layout (action log / viewport / chat+console)
 * plus a real, multi-step SOP runner on top of the same op infrastructure.
 * This is where "open the FreeCAD engine" happens (docs/CRAFTSMAN_AGENT.md). */
export function JobCraftsman() {
  const { jobId } = useParams<{ jobId: string }>();
  const location = useLocation();
  const suggestion = location.state as
    | { suggestedOp?: "fillet_wire"; suggestedRadius?: number; reason?: string }
    | null;
  const { data: job } = useJob(jobId);
  const craftsman = useCraftsman(jobId);
  const startLive = useStartLiveCraftsman(jobId);
  const liveOp = useLiveCraftsmanOp(jobId);
  const stopLive = useStopLiveCraftsman(jobId);
  const chat = useChat(jobId);

  const [log, setLog] = useState<LoggedAction[]>([]);
  const [viewerRuns, setViewerRuns] = useState(0);
  const [liveUrl, setLiveUrl] = useState<string | null>(null);
  const isLive = liveUrl !== null;

  // Runs ops through whichever transport is active - the live session
  // (one persistent document, real GUI redraws) once "Open live FreeCAD
  // engine" has been clicked, the one-shot headless path otherwise. Same
  // CraftsmanOp[] -> CraftsmanResponse shape either way, see
  // docs/CRAFTSMAN_AGENT.md's live-session section.
  const runOps = useMemo(
    () => (ops: CraftsmanOp[]): Promise<CraftsmanResponse> =>
      isLive ? liveOp.mutateAsync(ops) : craftsman.mutateAsync(ops),
    [isLive, liveOp, craftsman],
  );
  const opsPending = isLive ? liveOp.isPending : craftsman.isPending;
  const [tab, setTab] = useState<Tab>("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [sampleId, setSampleId] = useState("");
  const [deltaX, setDeltaX] = useState(100);
  const [mode, setMode] = useState<"offset" | "fillet">(
    suggestion?.suggestedOp === "fillet_wire" ? "fillet" : "offset",
  );
  const [radius, setRadius] = useState(suggestion?.suggestedRadius ?? 150);

  const [sopId, setSopId] = useState(SOPS[0].id);
  const sop = SOPS.find((s) => s.id === sopId) ?? SOPS[0];
  const [stepStatuses, setStepStatuses] = useState<StepStatus[]>(() => sop.steps.map(() => "pending"));
  const [sopRunning, setSopRunning] = useState(false);

  // Freshest response regardless of transport - liveOp.data once a live op
  // has run, the one-shot craftsman.data (initial snapshot or last headless
  // call) until then. Drives the object list, geometry/layer badge, and
  // whether the viewport has anything to show at all.
  const latestData = liveOp.data ?? craftsman.data;

  const geometryObjects = useMemo(
    () => (latestData?.objects ?? []).filter((o) => o.kind === "geometry"),
    [latestData],
  );

  async function goLive() {
    if (isLive || startLive.isPending) return;
    const res = await startLive.mutateAsync();
    setLiveUrl(res.html_url);
  }

  // Best-effort - the backend tears down the previous global session on
  // the next live/start anyway (see live_bridge.py), this just avoids
  // leaving a FreeCAD GUI process running for no reason after navigating
  // away.
  useEffect(() => {
    return () => {
      if (liveUrl) stopLive.mutate();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    setStepStatuses(sop.steps.map(() => "pending"));
  }, [sop]);

  // Auto-discover on load — the engineer shouldn't have to click before
  // seeing the plan; this is the "open the FreeCAD engine" moment.
  //
  // autoDiscoveredRef guards against firing this twice for the same job.
  // Without it, React StrictMode's dev-mode double-invoke (mount → cleanup
  // → mount) fires two concurrent POST /craftsman calls for the same job;
  // both run a real FreeCAD subprocess writing to the same job-keyed temp
  // paths (manipulated.dwg, craftsman.dxf), and they race — one comes back
  // 502. Confirmed hands-on (docs/CRAFTSMAN_AGENT.md §8): every "transient"
  // 502 seen while building this page was this race, not flakiness.
  const autoDiscoveredRef = useRef<string | null>(null);
  useEffect(() => {
    if (jobId && autoDiscoveredRef.current !== jobId) {
      autoDiscoveredRef.current = jobId;
      craftsman.mutate([], {
        onSuccess: (res) => {
          const first = res.objects.find((o) => o.kind === "geometry");
          if (first) setSampleId(first.id);
        },
      });
      setViewerRuns((n) => n + 1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  async function runOffset() {
    if (!sampleId) return;
    const op: CraftsmanOp = { op: "offset_wire", id: sampleId, delta: [deltaX, 0, 0] };
    const res = await runOps([op]);
    setLog((prev) => [{ op, result: res.op_results[0] }, ...prev].slice(0, 200));
    setViewerRuns((n) => n + 1);
  }

  async function runFillet() {
    if (!sampleId) return;
    const op: CraftsmanOp = { op: "fillet_wire", id: sampleId, radius, edge_indices: [0, 1] };
    const res = await runOps([op]);
    setLog((prev) => [{ op, result: res.op_results[0] }, ...prev].slice(0, 200));
    setViewerRuns((n) => n + 1);
  }

  // Every POST /craftsman call re-reads the original upload from scratch
  // (see docs/CRAFTSMAN_AGENT.md) — a multi-step SOP therefore can't chain
  // across *separate* calls (an id from call N doesn't exist in call N+1's
  // fresh document; confirmed hands-on: it fails with "unknown object id").
  // The correct shape is ONE call with every step's op in `ops`, chained
  // via the "$prev" sentinel (worker.py resolves it to whatever the
  // previous op in the SAME list just created) so this SOP doesn't have to
  // predict FreeCAD's own object-naming (upgrade → "Face" or "Wire"
  // depending on whether the source wire was closed, etc).
  async function runSop() {
    if (!sampleId || sopRunning) return;
    setSopRunning(true);
    setStepStatuses(sop.steps.map(() => "running"));
    const ops = sop.steps.map((step, i) => step.buildOp(i === 0 ? sampleId : "$prev"));
    try {
      const res = await runOps(ops);
      setStepStatuses(sop.steps.map((_, i) => (res.op_results[i]?.ok ? "done" : "failed")));
      setLog((prev) => [
        ...sop.steps
          .map((step, i) => ({ op: ops[i], result: res.op_results[i], step: `Step ${step.n}: ${step.title}` }))
          .reverse(),
        ...prev,
      ].slice(0, 200));
      setViewerRuns((n) => n + 1);
    } catch {
      setStepStatuses(sop.steps.map(() => "failed"));
    }
    setSopRunning(false);
  }

  function sendMessage() {
    const text = chatInput.trim();
    if (!text) return;
    setMessages((prev) => [...prev, { role: "user", text }]);
    setChatInput("");
    chat.mutate(text, {
      onSuccess: (res) => setMessages((prev) => [...prev, { role: "agent", text: res.reply }]),
      onError: () =>
        setMessages((prev) => [
          ...prev,
          { role: "agent", text: "Couldn't reach Plan Copilot — is the backend running?" },
        ]),
    });
  }

  return (
    <AppShell>
      <div className="flex h-full flex-col">
        {job && <Topbar jobId={job.id} filename={job.filename} status={job.status} />}
        <div className="flex min-h-0 flex-1 flex-col px-6 py-4">
          <div className="flex shrink-0 items-center gap-3">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-accent text-[10px] font-bold text-navy-950">
              CR
            </div>
            <h1 className="text-base font-semibold text-ink-primary">Craftsman Agent</h1>
            <span className="text-xs text-ink-muted">2D FreeCAD geometry engine</span>
            <div className="ml-auto flex items-center gap-2">
              {isLive && (
                <span className="rounded-full border border-accent/40 bg-accent/10 px-2.5 py-1 text-[11px] font-semibold text-accent">
                  ● Live FreeCAD
                </span>
              )}
              {(opsPending || sopRunning) && (
                <span className="rounded-full bg-accent/10 px-2.5 py-1 text-[11px] font-semibold text-accent">
                  {sopRunning ? `Running SOP (${sop.steps.length} steps)…` : "Running…"}
                </span>
              )}
              {latestData && !opsPending && !sopRunning && (
                <span className="rounded-full bg-accent/10 px-2.5 py-1 text-[11px] font-semibold text-accent">
                  {latestData.geometries.length} geometries · {latestData.layers.length} layers
                </span>
              )}
            </div>
          </div>

          {/* SOP runner */}
          <div className="mt-3 shrink-0 rounded-xl border border-line bg-navy-900 p-3.5">
            <div className="flex flex-wrap items-center gap-3">
              <select
                value={sopId}
                onChange={(e) => setSopId(e.target.value)}
                disabled={sopRunning}
                className="rounded-md border border-line bg-navy-950 px-2.5 py-1.5 text-xs font-medium text-ink-primary"
              >
                {SOPS.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
              <p className="min-w-0 flex-1 truncate text-xs text-ink-secondary">{sop.requirement}</p>
              <button
                onClick={runSop}
                disabled={!sampleId || sopRunning || opsPending}
                className="shrink-0 rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-navy-950 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {sopRunning ? "Running…" : `Run SOP (${sop.steps.length} steps)`}
              </button>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {sop.steps.map((step, i) => {
                const status = stepStatuses[i];
                const styles: Record<StepStatus, string> = {
                  pending: "border-line-light bg-navy-800 text-ink-muted",
                  running: "border-accent bg-accent/10 text-accent animate-pulse",
                  done: "border-accent/40 bg-accent/10 text-accent",
                  failed: "border-danger/40 bg-danger/10 text-danger",
                };
                const marks: Record<StepStatus, string> = { pending: "○", running: "◐", done: "✓", failed: "✕" };
                return (
                  <div
                    key={step.n}
                    title={step.description}
                    className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${styles[status]}`}
                  >
                    {marks[status]} {step.n}. {step.title}
                  </div>
                );
              })}
            </div>
          </div>

          {/* 3-pane grid — fills remaining page height */}
          <div className="mt-3 grid min-h-0 flex-1 grid-cols-1 gap-4 lg:grid-cols-[240px_minmax(0,1fr)_340px]">
            {/* action log */}
            <div className="min-h-0 overflow-auto rounded-xl border border-line bg-navy-900 p-3.5">
              <p className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-ink-muted">
                Action log
              </p>
              {log.length === 0 && (
                <p className="text-xs text-ink-muted">Run a step or an SOP to see it here.</p>
              )}
              <div className="space-y-3">
                {log.map((entry, i) => (
                  <div key={i} className="flex gap-2">
                    <div
                      className={`mt-0.5 h-4 w-4 shrink-0 rounded-full text-center text-[9px] font-bold leading-4 ${
                        entry.result.ok ? "bg-accent text-navy-950" : "bg-danger text-white"
                      }`}
                    >
                      {entry.result.ok ? "✓" : "✕"}
                    </div>
                    <div>
                      {entry.step && (
                        <p className="text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
                          {entry.step}
                        </p>
                      )}
                      <p className="text-xs font-medium text-ink-primary">{entry.result.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* viewport */}
            <div className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-navy-900">
              <div className="flex items-center gap-2.5 border-b border-line px-4 py-3 text-xs text-ink-secondary">
                <span className="truncate font-mono">
                  {job?.filename ?? "…"} — {isLive ? "live FreeCAD" : "FreeCAD viewer"}
                </span>
                {!isLive && (
                  <button
                    onClick={goLive}
                    disabled={startLive.isPending || !job}
                    className="ml-auto shrink-0 rounded-md border border-accent/40 px-2 py-1 text-[11px] font-semibold text-accent hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-40"
                    title="Open the real FreeCAD GUI, streamed live - ops redraw on screen as they run"
                  >
                    {startLive.isPending ? "Opening FreeCAD…" : "Open live FreeCAD engine ↗"}
                  </button>
                )}
                {job && latestData && (
                  <a
                    href={`${API_BASE_URL}${latestData.download_url}`}
                    className="shrink-0 text-accent hover:underline"
                  >
                    Download .dwg ↓
                  </a>
                )}
              </div>
              {startLive.isError && (
                <div className="shrink-0 border-b border-danger/40 bg-danger/10 px-4 py-2 text-[11px] text-danger">
                  Live FreeCAD not available — {(startLive.error as Error).message} Falling back to the
                  lightweight viewer below.
                </div>
              )}
              <div className="min-h-0 flex-1">
                {isLive && liveUrl ? (
                  <iframe title="Craftsman — live FreeCAD" src={liveUrl} className="h-full w-full border-0" />
                ) : job && latestData ? (
                  <iframe
                    key={viewerRuns}
                    title="Craftsman — FreeCAD viewer"
                    src={craftsmanViewerUrl(job.id)}
                    className="h-full w-full border-0"
                  />
                ) : (
                  <div className="flex h-full items-center justify-center text-xs text-ink-muted">
                    {craftsman.isPending ? "Opening the FreeCAD engine…" : "Waiting for the plan…"}
                  </div>
                )}
              </div>
              {suggestion?.reason && (
                <div className="shrink-0 border-t border-line bg-accent/5 px-3 py-2 text-[11px] text-ink-secondary">
                  <span className="font-semibold text-accent">Compliance Analyst suggests: </span>
                  {suggestion.reason} — fillet radius pre-filled below, pick the object to apply
                  it to.
                </div>
              )}
              <div className="flex shrink-0 flex-wrap items-end gap-2 border-t border-line p-3">
                <label className="text-xs text-ink-muted">
                  Object
                  <select
                    value={sampleId}
                    onChange={(e) => setSampleId(e.target.value)}
                    disabled={geometryObjects.length === 0 || sopRunning}
                    className="mt-1 block w-40 rounded-md border border-line bg-navy-950 px-2 py-1.5 text-xs text-ink-primary"
                  >
                    {geometryObjects.map((o) => (
                      <option key={o.id} value={o.id}>
                        {o.id} ({o.layer})
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex rounded-md border border-line-light p-0.5">
                  <button
                    onClick={() => setMode("offset")}
                    className={`rounded px-2 py-1 text-[11px] font-medium ${mode === "offset" ? "bg-accent text-navy-950" : "text-ink-secondary"}`}
                  >
                    Offset
                  </button>
                  <button
                    onClick={() => setMode("fillet")}
                    className={`rounded px-2 py-1 text-[11px] font-medium ${mode === "fillet" ? "bg-accent text-navy-950" : "text-ink-secondary"}`}
                  >
                    Fillet
                  </button>
                </div>
                {mode === "offset" ? (
                  <label className="text-xs text-ink-muted">
                    Δx (mm)
                    <input
                      type="number"
                      value={deltaX}
                      onChange={(e) => setDeltaX(Number(e.target.value))}
                      className="mt-1 block w-20 rounded-md border border-line bg-navy-950 px-2 py-1.5 text-xs text-ink-primary"
                    />
                  </label>
                ) : (
                  <label className="text-xs text-ink-muted">
                    Radius (mm)
                    <input
                      type="number"
                      value={radius}
                      onChange={(e) => setRadius(Number(e.target.value))}
                      className="mt-1 block w-20 rounded-md border border-line bg-navy-950 px-2 py-1.5 text-xs text-ink-primary"
                    />
                  </label>
                )}
                <button
                  onClick={mode === "offset" ? runOffset : runFillet}
                  disabled={!sampleId || opsPending || sopRunning}
                  className="rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-navy-950 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {mode === "offset" ? "Offset wire" : "Fillet corner"}
                </button>
              </div>
            </div>

            {/* chat / console */}
            <div className="flex min-h-0 flex-col overflow-hidden rounded-xl border border-line bg-navy-900">
              <div className="flex shrink-0 border-b border-line">
                <button
                  onClick={() => setTab("chat")}
                  className={`flex-1 py-2.5 text-center text-xs font-semibold ${
                    tab === "chat" ? "border-b-2 border-accent text-ink-primary" : "text-ink-muted"
                  }`}
                >
                  Ask about parts
                </button>
                <div className="w-px bg-line" />
                <button
                  onClick={() => setTab("console")}
                  className={`flex-1 py-2.5 text-center text-xs font-semibold ${
                    tab === "console" ? "border-b-2 border-accent text-ink-primary" : "text-ink-muted"
                  }`}
                >
                  Console
                </button>
              </div>
              {tab === "chat" ? (
                <>
                  <div className="flex min-h-0 flex-1 flex-col gap-2.5 overflow-auto p-3.5">
                    {messages.length === 0 && (
                      <p className="text-xs text-ink-muted">
                        Ask Plan Copilot about this plan — grounded in its regulation knowledge
                        bases, not a generic LLM call.
                      </p>
                    )}
                    {messages.map((m, i) => (
                      <div
                        key={i}
                        className={`max-w-[88%] rounded-lg px-3 py-2 text-xs leading-relaxed ${
                          m.role === "user"
                            ? "self-end bg-accent/20 text-ink-primary"
                            : "self-start bg-navy-800 text-ink-primary"
                        }`}
                      >
                        {m.text}
                      </div>
                    ))}
                  </div>
                  <div className="shrink-0 border-t border-line p-2.5">
                    <input
                      value={chatInput}
                      onChange={(e) => setChatInput(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && sendMessage()}
                      placeholder="Ask about the plan…"
                      className="w-full rounded-md border border-line bg-navy-950 px-2.5 py-2 text-xs text-ink-primary"
                    />
                  </div>
                </>
              ) : (
                <div className="min-h-0 flex-1 overflow-auto bg-navy-950 p-3.5 font-mono text-[11px] leading-relaxed text-ink-secondary">
                  {log.length === 0 ? (
                    <p className="text-ink-muted">
                      # No ops run yet — this is the literal FreeCAD API call each op below issues.
                    </p>
                  ) : (
                    log
                      .slice()
                      .reverse()
                      .map((entry, i) => (
                        <div key={i}>
                          <span className="text-ink-muted">{String(i + 1).padStart(2, "0")}</span>{" "}
                          {opToFreecadLine(entry.op)}
                        </div>
                      ))
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </AppShell>
  );
}
