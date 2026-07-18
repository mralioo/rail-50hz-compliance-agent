"""REST surface consumed by the Flutter Planner's Playground."""
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile

from app.agent.client import get_agent
from app.ingestion.storage import save_upload
from app.models.schemas import ChatRequest, ChatResponse, Job
from app.pipeline.orchestrator import job_store, run_pipeline

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


@router.post("/jobs/{job_id}/chat", response_model=ChatResponse)
def chat(job_id: str, request: ChatRequest) -> ChatResponse:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    reply = get_agent().chat(request.message, job.payload, job.report)
    return ChatResponse(reply=reply)
