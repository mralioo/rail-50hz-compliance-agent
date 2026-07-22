"""REST surface consumed by the Flutter Planner's Playground."""
import hashlib
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.agent.analyzer import analyze_hit, describe_hit
from app.agent.draftsman import DraftError, draw
from app.memory import history
from app.agent.client import get_agent
from app.agent.locator import locate
from app.extraction.renderer import load_render_meta, render_png
from app.ingestion.storage import save_upload
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    HitDescribeRequest,
    HitDescribeResponse,
    HitsAnalyzeRequest,
    HitsAnalyzeResponse,
    Job,
    DrawRequest,
    DrawResponse,
    LocateRequest,
    LocateResponse,
    SearchRecord,
)
from app.pipeline.orchestrator import job_store, render_path_for, run_pipeline


def _processed_job(job_id: str) -> Job:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.payload is None:
        raise HTTPException(status_code=409, detail="Plan not processed yet")
    return job

router = APIRouter(prefix="/api/v1")


@router.get("/health")
def health() -> dict:
    from app.core.config import get_settings

    return {"status": "ok", "agent_mode": get_settings().agent_mode}


@router.post("/jobs", response_model=Job)
async def create_job(file: UploadFile, background_tasks: BackgroundTasks) -> Job:
    if not file.filename or not file.filename.lower().endswith((".dwg", ".dxf")):
        raise HTTPException(status_code=400, detail="Upload a .dwg or .dxf file")
    job = job_store.create(file.filename)
    path = save_upload(job.id, file.filename, await file.read())
    background_tasks.add_task(run_pipeline, job, path)
    return job


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/jobs/{job_id}/render")
def get_render(job_id: str, layers: str | None = None) -> FileResponse:
    """Plan PNG; `?layers=a,b` renders only those layers (cached variants,
    same world window as the base render so overlays stay aligned)."""
    if job_store.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    base = render_path_for(job_id)
    if not base.exists():
        raise HTTPException(status_code=404, detail="No render available for this job")
    if not layers:
        return FileResponse(base, media_type="image/png")

    selected = {name for name in layers.split(",") if name}
    key = hashlib.md5(",".join(sorted(selected)).encode()).hexdigest()[:10]
    variant = base.parent / f"render_{key}.png"
    if not variant.exists():
        meta = load_render_meta(base)
        if not meta or "dxf" not in meta or not Path(meta["dxf"]).exists():
            raise HTTPException(status_code=404, detail="Source DXF no longer available")
        render_png(
            Path(meta["dxf"]), variant, layers=selected, world=tuple(meta["world"])
        )
    return FileResponse(variant, media_type="image/png")


@router.get("/searches", response_model=list[SearchRecord])
def search_history(limit: int = 20) -> list[SearchRecord]:
    return [SearchRecord(**row) for row in history.list_searches(limit)]


@router.post("/jobs/{job_id}/locate", response_model=LocateResponse)
def locate_component(job_id: str, request: LocateRequest) -> LocateResponse:
    job = _processed_job(job_id)
    result = locate(job.payload, request.query, load_render_meta(render_path_for(job_id)))
    history.save_search(job.id, job.filename, request.query, len(result.hits))
    return result


@router.post("/jobs/{job_id}/hits/analyze", response_model=HitsAnalyzeResponse)
def analyze_hits(job_id: str, request: HitsAnalyzeRequest) -> HitsAnalyzeResponse:
    """Deterministic per-hit overviews (no LLM — safe for every locate)."""
    job = _processed_job(job_id)
    return HitsAnalyzeResponse(
        analyses=[analyze_hit(job.payload, hit) for hit in request.hits]
    )


@router.post("/jobs/{job_id}/hits/describe", response_model=HitDescribeResponse)
def describe_one_hit(job_id: str, request: HitDescribeRequest) -> HitDescribeResponse:
    """AI description of a single hit — user-triggered only, to save tokens."""
    job = _processed_job(job_id)
    return HitDescribeResponse(
        description=describe_hit(job.payload, job.report, request.hit, request.analysis)
    )


@router.get("/jobs/{job_id}/render/meta")
def get_render_meta(job_id: str) -> dict:
    """World window + pixel size of the render (canvas coordinate mapping)."""
    if job_store.get(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")
    meta = load_render_meta(render_path_for(job_id))
    if meta is None:
        raise HTTPException(status_code=404, detail="No render available for this job")
    return {"world": meta["world"], "px": meta["px"]}


@router.post("/jobs/{job_id}/draw", response_model=DrawResponse)
def draw_element(job_id: str, request: DrawRequest) -> DrawResponse:
    """Draftsman agent: connect planner-clicked points as a sketch overlay."""
    _processed_job(job_id)
    try:
        return draw(
            request.instruction,
            request.points_image,
            load_render_meta(render_path_for(job_id)),
        )
    except DraftError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/jobs/{job_id}/chat", response_model=ChatResponse)
def chat(job_id: str, request: ChatRequest) -> ChatResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    reply = get_agent().chat(request.message, job.payload, job.report)
    return ChatResponse(reply=reply)
