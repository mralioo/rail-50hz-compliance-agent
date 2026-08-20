"""Shared API contract between the pipeline, the agent and the Flutter client.

The Dart models in `frontend/lib/models/` mirror these classes 1:1 — keep them
in sync when changing anything here.
"""
from enum import Enum

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "queued"
    CONVERTING = "converting"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    READY = "ready"
    FAILED = "failed"


# --------------------------------------------------------------------------- #
# Data layer (extraction output)
# --------------------------------------------------------------------------- #
class Geometry(BaseModel):
    layer: str
    kind: str  # "polyline" | "line" | "circle"
    points: list[tuple[float, float]]
    closed: bool = False
    radius: float | None = None  # circles only


class TextItem(BaseModel):
    layer: str
    text: str
    position: tuple[float, float]


class Metric(BaseModel):
    name: str
    value: float
    unit: str
    layer: str | None = None


class DataLayerPayload(BaseModel):
    source_file: str
    layers: list[str]
    geometries: list[Geometry]
    texts: list[TextItem]
    metrics: list[Metric]
    bounds: tuple[float, float, float, float] | None = None  # min_x, min_y, max_x, max_y


# --------------------------------------------------------------------------- #
# Compliance report (agent output)
# --------------------------------------------------------------------------- #
class FindingStatus(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    WARNING = "warning"


class FindingReview(BaseModel):
    """Engineer verify/flag state on a finding - separate from the agent's own
    FindingStatus judgement. Not persisted beyond the in-memory JobStore (same
    durability as everything else in this POC)."""

    status: str = "pending"  # "pending" | "verified" | "flagged"
    note: str | None = None
    reviewed_by: str | None = None


class Finding(BaseModel):
    status: FindingStatus
    parameter: str
    actual: str
    expected: str
    regulation: str
    location: str | None = None  # layer name or coordinates
    suggestion: str | None = None
    review: FindingReview = Field(default_factory=FindingReview)


class ComplianceReport(BaseModel):
    findings: list[Finding] = Field(default_factory=list)
    summary: str = ""


# --------------------------------------------------------------------------- #
# Job lifecycle & chat
# --------------------------------------------------------------------------- #
class Job(BaseModel):
    id: str
    status: JobStatus = JobStatus.QUEUED
    filename: str
    error: str | None = None
    payload: DataLayerPayload | None = None
    report: ComplianceReport | None = None
    created_at: str = ""  # ISO 8601, set once at JobStore.create - "Updated Xh ago" on project cards


class JobSummary(BaseModel):
    """Lightweight Job listing entry - no payload/report, safe to list many."""

    id: str
    filename: str
    status: JobStatus
    created_at: str = ""


class FindingReviewRequest(BaseModel):
    status: str  # "pending" | "verified" | "flagged"
    note: str | None = None
    reviewed_by: str | None = None


class ChatRequest(BaseModel):
    message: str
    # Browser-console-only field (see app/agent/rag.py::list_knowledge_bases);
    # None = ground on every knowledge base, same as before this field existed.
    # Not mirrored in the Flutter Dart models — it has no equivalent UI there.
    knowledge_bases: list[str] | None = None


class ChatResponse(BaseModel):
    reply: str


class KnowledgeBase(BaseModel):
    id: str
    name: str
    doc_count: int


# --------------------------------------------------------------------------- #
# Locator agent (visual grounding of chat queries on the plan)
# --------------------------------------------------------------------------- #
class LocateRequest(BaseModel):
    query: str
    # Optional highlight color for this locate's hits - a color name ("red",
    # "rot") or hex ("#e03131"/"e03131"), resolved by locator.py. Unset ->
    # annotate.py's default ACI yellow highlight layer, unchanged.
    color: str | None = None


class LocateHit(BaseModel):
    label: str
    source: str  # "text" (annotation) | "layer"
    confidence: float
    layer: str | None = None  # originating DXF layer
    anchor: tuple[float, float]  # world coordinates
    world_bbox: tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    # normalized [0..1] rect on the render image, y-down; None if no render
    image_bbox: tuple[float, float, float, float] | None = None
    # "#rrggbb", set from LocateRequest.color when given - per-hit so a
    # client round-tripping hits into /viewer/annotate carries the color
    # along with no extra state to track. None -> the default highlight color.
    color: str | None = None


class LocateResponse(BaseModel):
    query: str
    terms: list[str]
    hits: list[LocateHit]
    render_size: tuple[int, int] | None = None  # px, for aspect-true overlays


# --------------------------------------------------------------------------- #
# Analysis agent (per-hit deep dive; AI description only on user click)
# --------------------------------------------------------------------------- #
class HitAnalysis(BaseModel):
    """Deterministic overview of one located region — no LLM involved."""

    label: str
    layer: str | None = None
    bbox_size: tuple[float, float]  # drawing units (w, h)
    entity_count: int
    entities_by_kind: dict[str, int]
    layers: list[str]  # all layers present in the region
    annotations: list[str]  # texts found in/near the region
    metrics_summary: str


class HitsAnalyzeRequest(BaseModel):
    hits: list[LocateHit]


class HitsAnalyzeResponse(BaseModel):
    analyses: list[HitAnalysis]


class HitDescribeRequest(BaseModel):
    hit: LocateHit
    analysis: HitAnalysis | None = None


class HitDescribeResponse(BaseModel):
    description: str


# --------------------------------------------------------------------------- #
# Draftsman agent (planner clicks points, agent draws elements as overlays)
# --------------------------------------------------------------------------- #
class DrawRequest(BaseModel):
    instruction: str  # e.g. "draw the cable line NYY-J between the points"
    points_image: list[tuple[float, float]]  # normalized [0..1] render coords, y-down


class DrawnElement(BaseModel):
    id: str
    kind: str  # "cable_line" | "line" | ...
    label: str
    points_image: list[tuple[float, float]]
    points_world: list[tuple[float, float]]
    length: float  # drawing units (m by project convention)
    note: str  # rule reminders / geometry facts


class DrawResponse(BaseModel):
    element: DrawnElement
    reply: str  # chat-ready confirmation text


# --------------------------------------------------------------------------- #
# DWG manipulation (direct read/edit of the uploaded file via a CadEnginePort
# adapter, see app/domain/cad/ + app/adapters/cad/)
# --------------------------------------------------------------------------- #
class DwgReadResponse(BaseModel):
    source_file: str
    engine: str  # which CadEnginePort adapter produced this (e.g. "acadsharp")
    layers: list[str]
    geometries: list[Geometry]
    texts: list[TextItem]


class DwgEditOp(BaseModel):
    op: str  # "add_geometry" | "add_text" | "remove_geometry" | "remove_text"
    geometry: Geometry | None = None  # required for add_geometry
    text: TextItem | None = None  # required for add_text
    index: int | None = None  # required for remove_geometry / remove_text


class DwgManipulateRequest(BaseModel):
    edits: list[DwgEditOp]
    engine: str = "acadsharp"  # CadEnginePort adapter to read+write with
    version: str = "r2018"  # DWG version to write back (see CAD_ENGINE_FRAMEWORK.md)


class DwgManipulateResponse(BaseModel):
    engine: str
    version: str
    layers: list[str]
    geometries: list[Geometry]
    texts: list[TextItem]
    download_url: str  # GET this path for the manipulated .dwg


# --------------------------------------------------------------------------- #
# Craftsman agent (real 2D geometry ops via FreeCAD - offset/fillet/join;
# see docs/CRAFTSMAN_AGENT.md). Distinct from DwgEditOp above: those are flat
# add/remove of raw entities, these are genuine geometry transforms neither
# ezdxf nor ACadSharp can do.
# --------------------------------------------------------------------------- #
class CraftsmanOp(BaseModel):
    op: str  # "upgrade_objects" | "offset_wire" | "fillet_wire"
    # id/ids may be "$prev", meaning "the object the previous op in THIS
    # ops list created" - resolved by the worker (tools/freecad_worker/
    # worker.py). Only meaningful within one call: each POST /craftsman
    # re-reads the original upload from scratch, so an id from a prior call
    # doesn't exist in this one - $prev is how a multi-step SOP chains ops
    # without the caller predicting FreeCAD's own object-naming.
    ids: list[str] | None = None  # upgrade_objects: object ids to join
    id: str | None = None  # offset_wire / fillet_wire: object id to transform
    delta: list[float] | None = None  # offset_wire: [dx, dy, (dz)] in mm
    radius: float | None = None  # fillet_wire: corner radius in mm
    edge_indices: list[int] | None = None  # fillet_wire: the 2 adjacent edges to round


class CraftsmanRequest(BaseModel):
    ops: list[CraftsmanOp]
    dwg_version: str = "r2018"  # DWG version to write back (see CAD_ENGINE_FRAMEWORK.md)


class CraftsmanLiveStartResponse(BaseModel):
    """Real, embeddable FreeCAD GUI - see live_bridge.py/live_session.py and
    docs/CRAFTSMAN_AGENT.md. `html_url` is xpra's HTML5 client, put it in an
    iframe."""

    html_url: str


class CraftsmanResponse(BaseModel):
    layers: list[str]
    geometries: list[Geometry]
    texts: list[TextItem]
    objects: list[dict]  # {id, kind, layer} per geometry/text, same order - the
    # ids to target in a follow-up call's offset_wire/fillet_wire/upgrade_objects
    op_results: list[dict]  # per-op {op, ok, detail} - surfaces partial failures
    warnings: list[str]  # e.g. entities dropped for corrupt coordinates - see worker.py
    download_url: str  # GET this path for the manipulated .dwg (same route as /dwg/download)


# --------------------------------------------------------------------------- #
# Interactive viewer (cad-viewer export - see CAD_VIEWER_INTEGRATION.md)
# --------------------------------------------------------------------------- #
class ViewerAnnotateRequest(BaseModel):
    locate_hits: list[LocateHit] = Field(default_factory=list)
    drawn_elements: list[DrawnElement] = Field(default_factory=list)


class SearchRecord(BaseModel):
    """One saved locator search (history)."""

    ts: float
    job_id: str
    filename: str
    query: str
    hit_count: int
