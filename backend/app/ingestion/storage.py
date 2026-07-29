"""Upload staging.

Local disk for the MVP; swap `save_upload` for a GCS-backed implementation
(google-cloud-storage) when running behind Cloud Run without a persistent disk.
"""
import re
from pathlib import Path

from app.core.config import get_settings


def safe_upload_name(filename: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)


def upload_path_for(job_id: str, filename: str) -> Path:
    """Reconstructs the path save_upload wrote to, from job_id + Job.filename."""
    return get_settings().work_dir / job_id / safe_upload_name(filename)


def save_upload(job_id: str, filename: str, content: bytes) -> Path:
    target = upload_path_for(job_id, filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target
