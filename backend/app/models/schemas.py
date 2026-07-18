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
