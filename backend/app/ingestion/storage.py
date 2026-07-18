"""Upload staging.

Local disk for the MVP; swap `save_upload` for a GCS-backed implementation
(google-cloud-storage) when running behind Cloud Run without a persistent disk.
"""
import re
from pathlib import Path

from app.core.config import get_settings


def save_upload(job_id: str, filename: str, content: bytes) -> Path:
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name)
    job_dir = get_settings().work_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    target = job_dir / safe_name
    target.write_bytes(content)
    return target
