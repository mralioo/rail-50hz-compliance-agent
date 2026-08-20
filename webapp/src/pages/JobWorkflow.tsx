import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  addEdge,
  useNodesState,
  useEdgesState,
  useReactFlow,
  type Connection,
  type Edge,
  type Node,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AppShell } from "../components/layout/AppShell";
import { Topbar } from "../components/layout/Topbar";
import { PipelineFlowNode, type NodeState, type PipelineNodeData } from "../components/workflow/PipelineFlowNode";
import { PipelineFlowEdge, type PipelineEdgeData } from "../components/workflow/PipelineFlowEdge";
import { NodePalette } from "../components/workflow/NodePalette";
import { CanvasActionsProvider } from "../components/workflow/CanvasActionsContext";
import { NODE_DOCS, type NodeDoc } from "../content/nodeDocs";
import { useJob } from "../queries/useJob";
import { jobConsoleUrl } from "../api/jobs";
import type { JobStatus } from "../api/types";

const STAGE_ORDER: JobStatus[] = ["queued", "converting", "extracting", "analyzing", "ready"];

function stageState(status: JobStatus | undefined, stageIndex: number): NodeState {
  if (!status || status === "failed") return "pending";
  const current = STAGE_ORDER.indexOf(status);
  if (stageIndex < current) return "done";
  if (stageIndex === current) return "active";
  return "pending";
}

function descFor(name: string): string {
  return NODE_DOCS.find((d) => d.name === name)?.desc ?? "";
}

function seedNode(
  id: string,
  mono: string,
  title: string,
  subtitle: string,
  position: { x: number; y: number },
  extra: Partial<PipelineNodeData> = {},
): Node<PipelineNodeData> {
  return {
    id,
    type: "pipeline",
    position,
    data: {
      mono,
      title,
      subtitle,
      state: extra.state ?? (extra.alwaysDone ? "done" : "pending"),
      clickable: Boolean(extra.to),
      description: descFor(title),
      ...extra,
    },
  };
}

function seedEdge(id: string, source: string, target: string, description: string): Edge<PipelineEdgeData> {
  return { id, source, target, type: "pipeline", data: { description } };
}

type Template = "compliance" | "editor";

const COMPLIANCE_TEMPLATE: { nodes: Node<PipelineNodeData>[]; edges: Edge<PipelineEdgeData>[] } = {
  nodes: [
    seedNode("upload", "▲", "Upload", "Manual upload", { x: 0, y: 90 }, { alwaysDone: true }),
    seedNode("convert", "CV", "Convert", "DWG → DXF", { x: 220, y: 90 }, { stage: "converting" }),
    seedNode("extract", "EX", "Extract", "Layers, geometry, text", { x: 440, y: 90 }, { stage: "extracting" }),
    seedNode(
      "compliance",
      "CA",
      "Compliance Analyst",
      "Ril / VDE findings",
      { x: 660, y: 90 },
      { stage: "analyzing", to: "/findings" },
    ),
  ],
  edges: [
    seedEdge("e-upload-convert", "upload", "convert", "Uploaded file handed to the DWG → DXF converter."),
    seedEdge("e-convert-extract", "convert", "extract", "Converted DXF handed to the extraction parser."),
    seedEdge(
      "e-extract-compliance",
      "extract",
      "compliance",
      "Extracted layers/geometry/text checked against Ril/VDE regulation limits.",
    ),
  ],
};

const EDITOR_TEMPLATE: { nodes: Node<PipelineNodeData>[]; edges: Edge<PipelineEdgeData>[] } = {
  nodes: [
    seedNode("upload", "▲", "Upload", "Manual upload", { x: 0, y: 90 }, { alwaysDone: true }),
    seedNode("convert", "CV", "Convert", "DWG → DXF", { x: 220, y: 90 }, { stage: "converting" }),
    seedNode("extract", "EX", "Extract", "Layers, geometry, text", { x: 440, y: 90 }, { stage: "extracting" }),
    seedNode(
      "kb",
      "KB",
      "Knowledge Base",
      "Regulation corpora",
      { x: 660, y: 210 },
      { state: "done", to: "/sources" },
    ),
    seedNode(
      "craftsman",
      "CR",
      "Craftsman Agent",
      "Executes in FreeCAD",
      { x: 880, y: 90 },
      { stage: "ready", to: "/craftsman" },
    ),
  ],
  edges: [
    seedEdge("e-upload-convert", "upload", "convert", "Uploaded file handed to the DWG → DXF converter."),
    seedEdge("e-convert-extract", "convert", "extract", "Converted DXF handed to the extraction parser."),
    seedEdge(
      "e-extract-craftsman",
      "extract",
      "craftsman",
      "Extracted geometry is what the Craftsman agent's ops (offset/fillet/join) target.",
    ),
    seedEdge(
      "e-kb-craftsman",
      "kb",
      "craftsman",
      "Selected knowledge bases ground Craftsman's edits in the real regulation corpus.",
    ),
  ],
};

const TEMPLATES: Record<Template, { nodes: Node<PipelineNodeData>[]; edges: Edge<PipelineEdgeData>[] }> = {
  compliance: COMPLIANCE_TEMPLATE,
  editor: EDITOR_TEMPLATE,
};

const nodeTypes = { pipeline: PipelineFlowNode };
const edgeTypes = { pipeline: PipelineFlowEdge };

interface SavedLayout {
  template: Template;
  nodes: Node<PipelineNodeData>[];
  edges: Edge<PipelineEdgeData>[];
}

function layoutKey(jobId: string) {
  return `craftsman-workflow-layout:${jobId}`;
}

function loadLayout(jobId: string): SavedLayout | null {
  try {
    const raw = localStorage.getItem(layoutKey(jobId));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Older format was {positions, edges} with a fixed node set — no
    // `nodes`/`template`. Treat as absent rather than crashing ReactFlow.
    if (!Array.isArray(parsed?.nodes) || !parsed?.template) return null;
    return parsed as SavedLayout;
  } catch {
    return null;
  }
}

function saveLayout(jobId: string, payload: SavedLayout) {
  localStorage.setItem(layoutKey(jobId), JSON.stringify(payload));
}

/** Doc-derived route for an agent node added from the palette — the 4 that
 * live inside the Engineer's Console iframe (no standalone page). Craftsman
 * and Compliance Analyst are added directly with their real `to` by the
 * templates above; palette-added copies stay non-clickable reference nodes
 * (see NodePalette's docstring) except these, which have a genuine home. */
const CONSOLE_AGENTS = new Set(["Plan Copilot", "Locator", "Analyzer", "Draftsman"]);

function nodeFromPaletteDoc(doc: NodeDoc, position: { x: number; y: number }): Node<PipelineNodeData> {
  const disabled = doc.group === "Coming Soon";
  const to = CONSOLE_AGENTS.has(doc.name) ? "/console" : undefined;
  return {
    id: `${doc.mono}-${crypto.randomUUID().slice(0, 8)}`,
    type: "pipeline",
    position,
    data: {
      mono: doc.mono,
      title: doc.name,
      subtitle: doc.group,
      description: doc.desc,
      state: disabled ? "disabled" : "pending",
      badge: disabled ? "Soon" : undefined,
      clickable: Boolean(to),
      to,
    },
  };
}

function CanvasInner({
  jobId,
  status,
  template,
  initialNodes,
  initialEdges,
}: {
  jobId: string;
  status: JobStatus | undefined;
  template: Template;
  initialNodes: Node<PipelineNodeData>[];
  initialEdges: Edge<PipelineEdgeData>[];
}) {
  const navigate = useNavigate();
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const { deleteElements } = useReactFlow();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [pendingSourceId, setPendingSourceId] = useState<string | null>(null);

  // Live status drives each pipeline-stage node's `state` without disturbing
  // whatever position/connections the engineer has arranged. Nodes with no
  // `stage` (freeform palette additions, the KB connector, Coming Soon
  // nodes) are left exactly as they were created — this is what makes free
  // composition safe: adding a node never fights the live-status sync.
  useEffect(() => {
    setNodes((prev) =>
      prev.map((node) => {
        const d = node.data;
        if (d.state === "disabled") return node;
        if (d.alwaysDone) return d.state === "done" ? node : { ...node, data: { ...d, state: "done" as const } };
        if (!d.stage) return node;
        const state = stageState(status, STAGE_ORDER.indexOf(d.stage));
        return state === d.state ? node : { ...node, data: { ...d, state } };
      }),
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  // Persist the whole layout — nodes (identity + position + data), edges,
  // and which template it started from — per job. Full node objects, not
  // just positions, since node identity is no longer a fixed set once the
  // palette can add anything.
  useEffect(() => {
    saveLayout(jobId, { template, nodes, edges });
  }, [jobId, template, nodes, edges]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge({ ...connection, type: "pipeline" }, eds)),
    [setEdges],
  );

  const onNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      const to = (node.data as PipelineNodeData).to;
      if (to) navigate(`/app/jobs/${jobId}${to}`);
    },
    [jobId, navigate],
  );

  const openPalette = useCallback(() => {
    setPendingSourceId(null);
    setPaletteOpen(true);
  }, []);

  const closePalette = useCallback(() => {
    setPaletteOpen(false);
    setPendingSourceId(null);
  }, []);

  // n8n's "+" -after-a-node pattern: opens the same palette, but remembers
  // which node to auto-connect the next pick from.
  const addNodeFrom = useCallback((nodeId: string) => {
    setPendingSourceId(nodeId);
    setPaletteOpen(true);
  }, []);

  const deleteNode = useCallback(
    (nodeId: string) => deleteElements({ nodes: [{ id: nodeId }] }),
    [deleteElements],
  );

  const deleteEdge = useCallback(
    (edgeId: string) => deleteElements({ edges: [{ id: edgeId }] }),
    [deleteElements],
  );

  const handleAdd = useCallback(
    (doc: NodeDoc) => {
      const source = pendingSourceId ? nodes.find((n) => n.id === pendingSourceId) : undefined;
      const position = source
        ? { x: source.position.x + 240, y: source.position.y }
        : { x: 100 + (nodes.length % 5) * 190, y: 340 + Math.floor(nodes.length / 5) * 150 };
      const newNode = nodeFromPaletteDoc(doc, position);
      setNodes((prev) => [...prev, newNode]);
      if (source) {
        setEdges((prev) => [
          ...prev,
          { id: `e-${source.id}-${newNode.id}`, source: source.id, target: newNode.id, type: "pipeline" },
        ]);
      }
      closePalette();
    },
    [pendingSourceId, nodes, setNodes, setEdges, closePalette],
  );

  const connectFromTitle = pendingSourceId
    ? (nodes.find((n) => n.id === pendingSourceId)?.data.title ?? null)
    : null;

  const actions = { addNodeFrom, deleteNode, deleteEdge };

  return (
    <CanvasActionsProvider value={actions}>
      <div className="relative h-full w-full">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          colorMode="dark"
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} size={1} />
          <Controls showInteractive={false} />
        </ReactFlow>
        {!paletteOpen && (
          <button
            onClick={openPalette}
            className="absolute right-3 top-3 z-10 rounded-md border border-line-light bg-navy-900 px-3 py-1.5 text-xs font-semibold text-ink-primary shadow-lg hover:border-accent/40"
          >
            + Add node
          </button>
        )}
        <NodePalette
          open={paletteOpen}
          connectFromTitle={connectFromTitle}
          onAdd={handleAdd}
          onClose={closePalette}
        />
      </div>
    </CanvasActionsProvider>
  );
}

function TemplatePicker({ onPick }: { onPick: (t: Template) => void }) {
  const cards: { id: Template; title: string; desc: string }[] = [
    {
      id: "compliance",
      title: "Compliance Check",
      desc: "Upload → Convert → Extract → Compliance Analyst. Just verify the plan against Ril/VDE norms.",
    },
    {
      id: "editor",
      title: "Editor",
      desc: "Upload → Convert → Extract → Craftsman, with the job's Knowledge Base connected as grounding context — edit the plan with regulation context in hand.",
    },
  ];
  return (
    <div className="flex h-full items-center justify-center">
      <div className="w-full max-w-xl">
        <h2 className="text-center text-sm font-semibold text-ink-primary">Start this job's Main Workspace from…</h2>
        <p className="mt-1 text-center text-xs text-ink-muted">
          Picks a starting node layout — you can freely add, remove, and rewire nodes afterward.
        </p>
        <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {cards.map((c) => (
            <button
              key={c.id}
              onClick={() => onPick(c.id)}
              className="rounded-xl border border-line-light bg-navy-900 p-4 text-left transition-colors hover:border-accent/40 hover:bg-navy-800"
            >
              <p className="text-sm font-semibold text-ink-primary">{c.title}</p>
              <p className="mt-1.5 text-xs leading-relaxed text-ink-secondary">{c.desc}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

/** The job's Main Workspace: a real, editable, n8n-style node canvas — drag
 * nodes, draw/remove connections (including loop-backs), add any real
 * agent/pipeline-stage node from the palette, click a node with a real page
 * to open it. This is the sole per-job hub — every other job-scoped screen
 * (Sources/Findings/Craftsman/Console) is reached by clicking its node here,
 * not a top-level tab. Layout is freely editable and persists per job
 * (localStorage); it's for the engineer's own planning/reference — actual
 * execution always follows the fixed real pipeline for template-seeded
 * nodes regardless of how they're arranged, since there's no generic
 * workflow-graph backend behind this (see docs/CRAFTSMAN_AGENT.md's scope
 * notes). Nodes we don't have live yet (Graph/Vector DB writers) are shown
 * disabled rather than faked. */
export function JobWorkflow() {
  const { jobId } = useParams<{ jobId: string }>();
  const { data: job } = useJob(jobId);
  const [saved, setSaved] = useState<SavedLayout | null>(() => (jobId ? loadLayout(jobId) : null));

  const pickTemplate = useCallback(
    (t: Template) => {
      if (!jobId) return;
      const seed = TEMPLATES[t];
      const payload: SavedLayout = { template: t, nodes: seed.nodes, edges: seed.edges };
      saveLayout(jobId, payload);
      setSaved(payload);
    },
    [jobId],
  );

  return (
    <AppShell>
      <div className="flex h-full flex-col">
        {job && <Topbar jobId={job.id} filename={job.filename} status={job.status} />}
        <div className="flex items-center gap-3 border-b border-line bg-navy-900 px-6 py-2.5">
          <p className="text-xs text-ink-secondary">
            Drag nodes, draw or delete connections (loops allowed), add from the palette or a
            node's own “+”, hover ✕ to remove a node — hover anything for a description, click a
            node to open it.
          </p>
          {job && (
            <a
              href={jobConsoleUrl(job.id)}
              target="_blank"
              rel="noreferrer"
              className="ml-auto shrink-0 text-xs text-accent hover:underline"
            >
              Open Engineer&apos;s Console (Locator / Analyzer / Draftsman / Plan Copilot) ↗
            </a>
          )}
        </div>
        {job?.status === "failed" && (
          <div className="border-b border-danger/40 bg-danger/10 px-6 py-2 text-xs text-danger">
            Processing failed{job.error ? `: ${job.error}` : "."}
          </div>
        )}
        <div className="min-h-0 flex-1">
          {!jobId ? null : !saved ? (
            <TemplatePicker onPick={pickTemplate} />
          ) : (
            <ReactFlowProvider>
              <CanvasInner
                jobId={jobId}
                status={job?.status}
                template={saved.template}
                initialNodes={saved.nodes}
                initialEdges={saved.edges}
              />
            </ReactFlowProvider>
          )}
        </div>
      </div>
    </AppShell>
  );
}
