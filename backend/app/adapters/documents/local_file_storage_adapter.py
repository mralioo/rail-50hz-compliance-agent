"""
LocalFileStorageAdapter — Adapter layer.

Implements ``FileStoragePort`` against the local filesystem. This is the
"artifact store" for this project: no S3/Garage/Postgres deployed, so
extracted text and images are written as plain files under a root directory
(``dataset/clean/`` for the ingestion pipeline) and addressed by the same key
convention the port defines everywhere else — swapping in an S3-backed
adapter later needs no change above this layer.

A key is a POSIX-style relative path (e.g.
``"ESTW-A Dörstewitz/Erdungsanlage/2333116242_Info/images/000_p001_ab12cd34.png"``).
The returned URI is ``file://<absolute-path>``.
"""
from pathlib import Path
from typing import Optional
from urllib.parse import quote, unquote, urlparse

from app.domain.documents.ports import FileStoragePort


class LocalFileStorageAdapter(FileStoragePort):
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def _path_for(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if self._root.resolve() not in path.parents and path != self._root.resolve():
            raise ValueError(f"key escapes storage root: {key!r}")
        return path

    async def store(
        self,
        *,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        path = self._path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"file://{quote(str(path))}"

    async def retrieve(self, *, key: str) -> Optional[bytes]:
        path = self._path_for(key)
        if not path.exists():
            return None
        return path.read_bytes()

    async def delete(self, *, key: str) -> None:
        path = self._path_for(key)
        path.unlink(missing_ok=True)

    async def exists(self, *, key: str) -> bool:
        return self._path_for(key).exists()

    async def list_keys(self, *, prefix: str) -> list[str]:
        base = self._path_for(prefix)
        search_root = base if base.is_dir() else base.parent
        if not search_root.exists():
            return []
        return [
            str(p.relative_to(self._root).as_posix())
            for p in search_root.rglob("*")
            if p.is_file() and str(p.relative_to(self._root).as_posix()).startswith(prefix)
        ]

    @staticmethod
    def path_from_uri(uri: str) -> Path:
        """Recover the filesystem path from a ``file://`` URI this adapter returned."""
        return Path(unquote(urlparse(uri).path))
