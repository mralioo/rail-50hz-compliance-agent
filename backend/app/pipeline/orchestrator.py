"""End-to-end pipeline: convert -> extract -> compute -> analyze.

Jobs live in an in-memory store (fine for a single Cloud Run instance / local
dev). Swap `JobStore` for Firestore/Redis when scaling out.
"""
import threading
import uuid
from pathlib import Path

from app.agent.client import get_agent
from app.core.config import get_settings
from app.extraction.dxf_parser import parse_dxf
from app.extraction.geometry import compute_bounds, compute_metrics
from app.extraction.renderer import render_png
from app.ingestion.converter import ensure_dxf
from app.models.schemas import DataLayerPayload, Job, JobStatus


def render_path_for(job_id: str) -> Path:
    return get_settings().work_dir / job_id / "render.png"


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, filename: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], filename=filename)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def update(self, job: Job) -> None:
        with self._lock:
            self._jobs[job.id] = job


job_store = JobStore()


def run_pipeline(job: Job, source_path: Path) -> None:
    try:
        job.status = JobStatus.CONVERTING
        job_store.update(job)
        dxf_path = ensure_dxf(source_path)

        job.status = JobStatus.EXTRACTING
        job_store.update(job)
        try:  # render is best-effort; the data pipeline never fails because of it
            render_png(dxf_path, render_path_for(job.id))
        except Exception:
            pass
        layers, geometries, texts = parse_dxf(dxf_path)
        job.payload = DataLayerPayload(
            source_file=job.filename,
            layers=layers,
            geometries=geometries,
            texts=texts,
            metrics=compute_metrics(geometries, texts),
            bounds=compute_bounds(geometries),
        )

        job.status = JobStatus.ANALYZING
        job_store.update(job)
        job.report = get_agent().analyze(job.payload)

        job.status = JobStatus.READY
    except Exception as exc:  # surface any stage failure to the client
        job.status = JobStatus.FAILED
        job.error = str(exc)
    finally:
        job_store.update(job)
