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


class Finding(BaseModel):
    status: FindingStatus
    parameter: str
    actual: str
    expected: str
    regulation: str
    location: str | None = None  # layer name or coordinates
    suggestion: str | None = None


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


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


# --------------------------------------------------------------------------- #
# Locator agent (visual grounding of chat queries on the plan)
# --------------------------------------------------------------------------- #
class LocateRequest(BaseModel):
    query: str


class LocateHit(BaseModel):
    label: str
    source: str  # "text" (annotation) | "layer"
    confidence: float
    layer: str | None = None  # originating DXF layer
    anchor: tuple[float, float]  # world coordinates
    world_bbox: tuple[float, float, float, float]  # min_x, min_y, max_x, max_y
    # normalized [0..1] rect on the render image, y-down; None if no render
    image_bbox: tuple[float, float, float, float] | None = None


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


class SearchRecord(BaseModel):
    """One saved locator search (history)."""

    ts: float
    job_id: str
    filename: str
    query: str
    hit_count: int
