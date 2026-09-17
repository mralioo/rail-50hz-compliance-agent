"""REST surface consumed by the Flutter Planner's Playground."""
import hashlib
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from app.adapters.cad.acadsharp_adapter import AcadSharpEngine
from app.adapters.cad.ezdxf_adapter import EzdxfEngine
from app.agent import rag
from app.agent.analyzer import analyze_hit, describe_hit
from app.agent.draftsman import DraftError, draw
from app.bootstrap import get_cad_engine
from app.core.config import get_settings
from app.core.debug_log import debug_log
from app.craftsman import freecad_bridge, live_bridge
from app.craftsman.freecad_bridge import CraftsmanError
from app.domain.cad.ports import EngineError
from app.domain.cad.services import EditError, apply_edits
from app.memory import history
from app.agent.client import get_agent
from app.agent.locator import locate
from app.extraction.renderer import load_render_meta, render_png
from app.ingestion.converter import ensure_dxf
from app.ingestion.storage import save_upload, upload_path_for
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    CraftsmanLiveStartResponse,
    CraftsmanRequest,
    CraftsmanResponse,
    DwgManipulateRequest,
    DwgManipulateResponse,
    DwgReadResponse,
    Finding,
    FindingReviewRequest,
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
    craftsman_dxf_path_for,
    craftsman_viewer_path_for,
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
        JobSummary(id=j.id, filename=j.filename, status=j.status, created_at=j.created_at)
        for j in job_store.list_recent(limit)
    ]


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/jobs/{job_id}")
def delete_job(job_id: str) -> dict:
    """Removes the job and its whole work_dir (upload, render, manipulated
    .dwg, viewer caches) - permanent, no undo (same durability level as the
    rest of this in-memory-store POC). Stops the live Craftsman session
    first if it belongs to this job, so a deleted job's DXF doesn't stay
    open in an orphaned FreeCAD process."""
    if not job_store.delete(job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    if live_bridge.current_job_id() == job_id:
        live_bridge.stop_live_session()
    shutil.rmtree(get_settings().work_dir / job_id, ignore_errors=True)
    return {"ok": True}


@router.patch("/jobs/{job_id}/findings/{index}/review", response_model=Finding)
def review_finding(job_id: str, index: int, request: FindingReviewRequest) -> Finding:
    """Engineer verify/flag state on one finding - separate from the agent's
    own compliant/non_compliant/warning judgement. Folded into the finding
    itself so GET /jobs/{id} returns it for free; no separate fetch needed."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.report is None or not (0 <= index < len(job.report.findings)):
        raise HTTPException(status_code=404, detail="Finding not found")
    if request.status not in ("pending", "verified", "flagged"):
        raise HTTPException(status_code=422, detail="status must be pending, verified, or flagged")
    finding = job.report.findings[index]
    finding.review.status = request.status
    finding.review.note = request.note
    finding.review.reviewed_by = request.reviewed_by
    job_store.update(job)
    return finding


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
    """Reads the originally uploaded file straight through a CadEnginePort
    adapter (layers/geometries/texts) — independent of the extraction
    pipeline's DataLayerPayload. `?engine=` picks which one (see
    docs/CAD_ENGINE_FRAMEWORK.md); default is ACadSharp, the only engine
    that round-trips DWG reliably."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = _source_path(job)
    try:
        cad_engine = get_cad_engine(engine)
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
        cad_engine = get_cad_engine(request.engine)
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


@router.post("/jobs/{job_id}/craftsman", response_model=CraftsmanResponse)
def craftsman_manipulate(job_id: str, request: CraftsmanRequest) -> CraftsmanResponse:
    """Reads the uploaded DWG/DXF, runs real 2D geometry ops (offset/fillet/
    join wires) through the FreeCAD-backed Craftsman agent, writes a new
    .dwg (fetch it from `download_url`, the same route `/dwg/manipulate`
    uses). Each call re-reads the original upload - ops don't accumulate
    across calls. Call once with `ops: []` to get an object-id snapshot
    (`objects`) before targeting a real op at a specific id. See
    docs/CRAFTSMAN_AGENT.md."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = _source_path(job)
    try:
        dxf_in = ensure_dxf(path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    try:
        result = freecad_bridge.run_job(dxf_in, request.ops)
    except CraftsmanError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    drawing = freecad_bridge.to_parsed_drawing(result)
    try:
        AcadSharpEngine().write(drawing, manipulated_dwg_path_for(job_id), version=request.dwg_version)
        # Also a plain DXF snapshot, purely so /craftsman/viewer below has
        # something to feed the existing cad-viewer exporter (it takes DXF,
        # not our ParsedDrawing JSON) - not used for the DWG deliverable.
        EzdxfEngine().write(drawing, craftsman_dxf_path_for(job_id))
    except EngineError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    craftsman_viewer_path_for(job_id).unlink(missing_ok=True)  # stale from a previous call

    for r in result["op_results"]:
        debug_log.record_command(job_id, "headless", r["op"], r["ok"], r["detail"])

    return CraftsmanResponse(
        layers=drawing.layers,
        geometries=drawing.geometries,
        texts=drawing.texts,
        objects=result.get("objects", []),
        op_results=result["op_results"],
        warnings=result.get("warnings", []),
        download_url=f"/api/v1/jobs/{job_id}/dwg/download",
    )


@router.post("/jobs/{job_id}/craftsman/live/start", response_model=CraftsmanLiveStartResponse)
def craftsman_live_start(job_id: str) -> CraftsmanLiveStartResponse:
    """Starts a real, persistent FreeCAD GUI session for this job, streamed
    into the browser via xpra's HTML5 client (`html_url`, put it in an
    iframe) - ops run against one document that stays open the whole
    session, so edits redraw live instead of only appearing after a fresh
    viewer reload. One global session at a time (see live_bridge.py) -
    starting this tears down any other job's live session first."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = _source_path(job)
    try:
        dxf_in = ensure_dxf(path)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    try:
        html_url = live_bridge.start_live_session(job_id, dxf_in)
    except CraftsmanError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    return CraftsmanLiveStartResponse(html_url=html_url)


@router.post("/jobs/{job_id}/craftsman/live/op", response_model=CraftsmanResponse)
def craftsman_live_op(job_id: str, request: CraftsmanRequest) -> CraftsmanResponse:
    """Sends ops to the running live FreeCAD session (see .../live/start) -
    same request/response shape as POST .../craftsman, different transport.
    Also refreshes the lightweight viewer/download artifacts so they stay
    in sync while the engineer is driving the live session."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    ops = [op.model_dump(exclude_none=True) for op in request.ops]
    try:
        result = live_bridge.send_live_op(ops)
    except CraftsmanError as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    drawing = freecad_bridge.to_parsed_drawing(result)
    try:
        AcadSharpEngine().write(drawing, manipulated_dwg_path_for(job_id), version=request.dwg_version)
        EzdxfEngine().write(drawing, craftsman_dxf_path_for(job_id))
    except EngineError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
    craftsman_viewer_path_for(job_id).unlink(missing_ok=True)  # stale from a previous call

    for r in result["op_results"]:
        debug_log.record_command(job_id, "live", r["op"], r["ok"], r["detail"])

    return CraftsmanResponse(
        layers=drawing.layers,
        geometries=drawing.geometries,
        texts=drawing.texts,
        objects=result.get("objects", []),
        op_results=result["op_results"],
        warnings=result.get("warnings", []),
        download_url=f"/api/v1/jobs/{job_id}/dwg/download",
    )


@router.post("/jobs/{job_id}/craftsman/live/stop")
def craftsman_live_stop(job_id: str) -> dict:
    """Tears down the live FreeCAD session, if any (job_id kept in the path
    for symmetry with start/op - there's only ever one global session, see
    live_bridge.py)."""
    live_bridge.stop_live_session()
    return {"ok": True}


@router.get("/jobs/{job_id}/craftsman/viewer")
def get_craftsman_viewer(job_id: str) -> HTMLResponse:
    """Same interactive cad-viewer as `/jobs/{id}/viewer`, but rendering the
    Craftsman agent's latest result (see POST .../craftsman) instead of the
    original upload - the offset/fillet/join changes visible, pan/zoom/
    measure included. Generated once per craftsman call, cached until the
    next one (see the `unlink` above)."""
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    dxf_path = craftsman_dxf_path_for(job_id)
    if not dxf_path.exists():
        raise HTTPException(
            status_code=404,
            detail="No Craftsman result yet for this job — call POST .../craftsman first",
        )
    out_path = craftsman_viewer_path_for(job_id)
    if not out_path.exists():
        try:
            export_html(dxf_path, out_path, title=f"{job.filename} (Craftsman)")
        except CadViewerError as exc:
            raise HTTPException(status_code=502, detail=str(exc))
    return HTMLResponse(out_path.read_text())


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


# --------------------------------------------------------------------------- #
# Debug Console - live session health, request/command traffic, xpra log tail.
# In-memory only (app/core/debug_log.py), same durability as the rest of
# this POC. See docs/CRAFTSMAN_AGENT.md's debug-mode section.
# --------------------------------------------------------------------------- #
@router.get("/debug/session")
def debug_session() -> dict:
    return {"session": live_bridge.session_status()}


@router.get("/debug/requests")
def debug_requests() -> list[dict]:
    return debug_log.requests()


@router.get("/debug/commands")
def debug_commands() -> list[dict]:
    return debug_log.commands()


@router.get("/debug/xpra-log")
def debug_xpra_log(lines: int = 200) -> dict:
    log_path = get_settings().work_dir / "craftsman_live_xpra.log"
    if not log_path.exists():
        return {"path": str(log_path), "lines": []}
    content = log_path.read_text(errors="replace").splitlines()
    return {"path": str(log_path), "lines": content[-lines:]}
