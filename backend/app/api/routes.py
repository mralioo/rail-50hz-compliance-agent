"""REST surface consumed by the Flutter Planner's Playground."""
import hashlib
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.agent import rag
from app.agent.analyzer import analyze_hit, describe_hit
from app.agent.draftsman import DraftError, draw
from app.cad_engines import EngineError, get_engine
from app.cad_engines.manipulate import EditError, apply_edits
from app.memory import history
from app.agent.client import get_agent
from app.agent.locator import locate
from app.extraction.renderer import load_render_meta, render_png
from app.ingestion.storage import save_upload, upload_path_for
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    DwgManipulateRequest,
    DwgManipulateResponse,
    DwgReadResponse,
    HitDescribeRequest,
    HitDescribeResponse,
    HitsAnalyzeRequest,
    HitsAnalyzeResponse,
    Job,
    JobSummary,
    KnowledgeBase,
    DrawRequest,
    DrawResponse,
    LocateRequest,
    LocateResponse,
    SearchRecord,
    ViewerAnnotateRequest,
)
from app.pipeline.orchestrator import (
    job_store,
    manipulated_dwg_path_for,
    render_path_for,
    run_pipeline,
    viewer_path_for,
)
from app.viewer import (
    CadViewerError,
    build_annotated_dxf,
    export_html,
    render_console_shell,
    render_console_upload,
)


def _processed_job(job_id: str) -> Job:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.payload is None:
        raise HTTPException(status_code=409, detail="Plan not processed yet")
    return job


def _source_path(job: Job) -> Path:
    """The originally uploaded file (.dwg or .dxf), independent of the
    converted-to-DXF copy the extraction pipeline works from."""
    path = upload_path_for(job.id, job.filename)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Original upload no longer available")
    return path


def _canonical_dxf_path(job_id: str) -> Path:
    """The DXF the pipeline actually rendered/extracted from (same source
    the renderer and locator agent use) - so viewer annotations line up in
    the same coordinate space as locate hits' world_bbox values."""
    meta = load_render_meta(render_path_for(job_id))
    if meta is None or "dxf" not in meta or not Path(meta["dxf"]).exists():
        raise HTTPException(status_code=404, detail="No processed DXF available for this job")
    return Path(meta["dxf"])


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


@router.get("/jobs", response_model=list[JobSummary])
def list_jobs(limit: int = 10) -> list[JobSummary]:
    return [
        JobSummary(id=j.id, filename=j.filename, status=j.status)
        for j in job_store.list_recent(limit)
    ]


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
    result = locate(
        job.payload, request.query, load_render_meta(render_path_for(job_id)), request.color
    )
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


@router.get("/jobs/{job_id}/dwg", response_model=DwgReadResponse)
def read_dwg(job_id: str, engine: str = "acadsharp") -> DwgReadResponse:
    """Reads the originally uploaded file straight through a cad_engines
    engine (layers/geometries/texts) — independent of the extraction
    pipeline's DataLayerPayload. `?engine=` picks which one (see
    docs/CAD_ENGINE_FRAMEWORK.md); default is ACadSharp, the only engine
    that round-trips DWG reliably."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = _source_path(job)
    try:
        cad_engine = get_engine(engine)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not cad_engine.can_read(path):
        raise HTTPException(
            status_code=400, detail=f"Engine '{engine}' cannot read {path.suffix} files"
        )
    try:
        drawing = cad_engine.read(path)
    except EngineError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return DwgReadResponse(
        source_file=job.filename,
        engine=engine,
        layers=drawing.layers,
        geometries=drawing.geometries,
        texts=drawing.texts,
    )


@router.post("/jobs/{job_id}/dwg/manipulate", response_model=DwgManipulateResponse)
def manipulate_dwg(job_id: str, request: DwgManipulateRequest) -> DwgManipulateResponse:
    """Reads the uploaded DWG/DXF, applies `edits`, writes a new .dwg (fetch
    it from `download_url`). Each call re-reads the original upload — edits
    don't accumulate across calls, send the full list you want applied."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = _source_path(job)
    try:
        cad_engine = get_engine(request.engine)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not cad_engine.can_read(path):
        raise HTTPException(
            status_code=400, detail=f"Engine '{request.engine}' cannot read {path.suffix} files"
        )
    if not cad_engine.writes_dwg:
        raise HTTPException(
            status_code=400, detail=f"Engine '{request.engine}' cannot write DWG"
        )

    try:
        drawing = cad_engine.read(path)
        apply_edits(drawing, request.edits)
        out_path = manipulated_dwg_path_for(job_id)
        cad_engine.write(drawing, out_path, version=request.version)
    except EngineError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    except EditError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return DwgManipulateResponse(
        engine=request.engine,
        version=request.version,
        layers=drawing.layers,
        geometries=drawing.geometries,
        texts=drawing.texts,
        download_url=f"/api/v1/jobs/{job_id}/dwg/download",
    )


@router.get("/jobs/{job_id}/dwg/download")
def download_dwg(job_id: str) -> FileResponse:
    path = manipulated_dwg_path_for(job_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="No manipulated DWG for this job yet")
    return FileResponse(
        path, media_type="application/acad", filename=f"{job_id}_manipulated.dwg"
    )


@router.get("/jobs/{job_id}/viewer")
def get_viewer(job_id: str) -> HTMLResponse:
    """Self-contained interactive viewer (cad-viewer: pan/zoom/measure/
    layers) for this job's plan - no agent annotations. Generated once and
    cached to disk; see docs/CAD_VIEWER_INTEGRATION.md."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    out_path = viewer_path_for(job_id)
    if not out_path.exists():
        dxf_path = _canonical_dxf_path(job_id)
        try:
            export_html(dxf_path, out_path, title=job.filename)
        except CadViewerError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    return HTMLResponse(out_path.read_text())


@router.get("/console")
def get_console_upload() -> HTMLResponse:
    """Job-id-less landing page: drag-and-drop or pick any real .dwg/.dxf
    file, which is uploaded through the normal POST /jobs pipeline and then
    redirects into that job's console once processing finishes."""
    return HTMLResponse(render_console_upload())


@router.get("/jobs/{job_id}/console")
def get_console(job_id: str) -> HTMLResponse:
    """The engineer's console: chat/findings/history/sketch/knowledge-base
    sidebar wrapped around the bare cad-viewer export (see /viewer). Not
    cached - pure string substitution, no subprocess work."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return HTMLResponse(render_console_shell(job_id, job.filename))


@router.post("/jobs/{job_id}/viewer/annotate")
def annotate_viewer(job_id: str, request: ViewerAnnotateRequest) -> HTMLResponse:
    """Same interactive viewer, with locator hits and/or draftsman sketches
    baked in as real, highlighted DXF entities (not a raster overlay) -
    regenerated fresh on every call, not cached."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    dxf_path = _canonical_dxf_path(job_id)
    with tempfile.TemporaryDirectory() as tmp:
        annotated = Path(tmp) / "annotated.dxf"
        build_annotated_dxf(
            dxf_path, annotated,
            locate_hits=request.locate_hits,
            drawn_elements=request.drawn_elements,
        )
        out_html = Path(tmp) / "viewer.html"
        try:
            export_html(annotated, out_html, title=job.filename)
        except CadViewerError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
        html = out_html.read_text()
    return HTMLResponse(html)


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
    reply = get_agent().chat(
        request.message, job.payload, job.report, kb_ids=request.knowledge_bases
    )
    return ChatResponse(reply=reply)


@router.get("/knowledge-bases", response_model=list[KnowledgeBase])
def list_knowledge_bases() -> list[KnowledgeBase]:
    return rag.list_knowledge_bases()
