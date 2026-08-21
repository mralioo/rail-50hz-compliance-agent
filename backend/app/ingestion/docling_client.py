"""Low-level HTTP client for the Docling document-conversion service.

Ported from the ITUKI backend (infrastructure/clients/docling_client.py) so
this project's dataset extraction uses the *same* server API and the *same*
call/polling mechanism instead of running Docling's ML pipeline locally on
CPU (~15-22s/page, and no image extraction).

The service runs at ``DOCLING_BASE_URL`` (default ``http://10.0.1.236/docling``)
and exposes an async job API:

    POST /v1/chunk/hybrid/file/async   -> {"task_id": ...}
    GET  /v1/status/poll/{task_id}     -> {"task_status": "success"|...}
    GET  /v1/result/{task_id}          -> {chunks, documents:[{content:{...}}]}

``chunk_file_with_images`` submits a single job with image export enabled and
returns three things from one call: the hybrid-chunked text, the full
Markdown, and the converted-document JSON (whose page renders the pipeline
crops individual pictures out of - Docling does not embed per-picture bytes
even with ``image_export_mode=embedded``).
"""
import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx


@dataclass
class ChunkResult:
    """One chunk from Docling's hybrid chunker.

    ``text`` carries the raw (non-contextualized) chunk content so it stays
    within the chunker's token budget.
    """

    text: str
    chunk_index: int = 0
    num_tokens: int | None = None
    headings: list[str] = field(default_factory=list)
    captions: list[str] = field(default_factory=list)
    page_numbers: list[int] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversionResult:
    """Everything one ``chunk_file_with_images`` call yields."""

    chunks: list[ChunkResult]
    markdown: str
    document: dict  # raw Docling document JSON (pages + pictures live here)


class DoclingClient:
    """Async HTTP client for the Docling conversion service.

    Submits documents via multipart/form-data to the async job API and polls
    for completion, matching the ITUKI backend's proven call sequence.
    """

    def __init__(
        self,
        base_url: str = "http://10.0.1.236/docling",
        *,
        timeout: float = 1800.0,  # 30 min read - AEC schematics render slowly
        poll_interval: float = 5.0,
        max_poll_attempts: int = 720,  # 720 * 5s = 60 min max wait
        embedding_model: str = "intfloat/multilingual-e5-large",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.poll_interval = poll_interval
        self.max_poll_attempts = max_poll_attempts
        self.embedding_model = embedding_model

        self.health_url = f"{self.base_url}/health"
        self.status_poll_url = f"{self.base_url}/v1/status/poll"
        self.result_url = f"{self.base_url}/v1/result"
        self.chunk_hybrid_file_async_url = f"{self.base_url}/v1/chunk/hybrid/file/async"

    def _timeout_config(self) -> httpx.Timeout:
        return httpx.Timeout(
            connect=60.0, read=self.timeout, write=self.timeout, pool=30.0
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.health_url)
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def chunk_file_with_images(
        self,
        file_bytes: bytes,
        filename: str,
        *,
        max_tokens: int = 512,
        force_ocr: bool = False,
        ocr_lang: list[str] | None = None,
        images_scale: float = 2.0,
        classify_pictures: bool = True,
        describe_pictures: bool = False,
        picture_description_prompt: str | None = None,
        merge_peers: bool = True,
    ) -> ConversionResult:
        """Chunk a document and extract embedded images in a single API call.

        Returns text chunks, the full Markdown, and the converted-document
        JSON (page renders + picture provenance the pipeline crops from).
        """
        if not filename:
            raise ValueError("filename is required for chunk_file_with_images")

        async with httpx.AsyncClient(timeout=self._timeout_config()) as client:
            task_id = await self._submit(
                client,
                filename=filename,
                file_bytes=file_bytes,
                max_tokens=max_tokens,
                force_ocr=force_ocr,
                ocr_lang=ocr_lang,
                images_scale=images_scale,
                classify_pictures=classify_pictures,
                describe_pictures=describe_pictures,
                picture_description_prompt=picture_description_prompt,
                merge_peers=merge_peers,
            )
            await self._wait_for_completion(client, task_id)
            return await self._get_result(client, task_id)

    async def _submit(
        self,
        client: httpx.AsyncClient,
        *,
        filename: str,
        file_bytes: bytes,
        max_tokens: int,
        force_ocr: bool,
        ocr_lang: list[str] | None,
        images_scale: float,
        classify_pictures: bool,
        describe_pictures: bool,
        picture_description_prompt: str | None,
        merge_peers: bool,
    ) -> str:
        files = {"files": (filename, file_bytes, "application/octet-stream")}
        # `data` must be a dict, not a list of tuples: httpx builds a sync-only
        # multipart stream from list-of-tuples form data, which an AsyncClient
        # then refuses to send ("Attempted to send an sync request..."). A dict
        # works, and httpx still expands list *values* into repeated form
        # fields - which is how the Docling API takes array params like
        # convert_ocr_lang.
        data: dict[str, Any] = {
            "convert_do_ocr": "true",
            "convert_force_ocr": str(force_ocr).lower(),
            "convert_ocr_engine": "easyocr",
            "convert_pdf_backend": "dlparse_v4",
            "convert_table_mode": "accurate",
            "convert_do_table_structure": "true",
            "convert_include_images": "true",
            "convert_image_export_mode": "embedded",
            "convert_images_scale": str(images_scale),
            "convert_do_picture_classification": str(classify_pictures).lower(),
            "convert_do_picture_description": str(describe_pictures).lower(),
            "convert_document_timeout": str(self.timeout),
            "convert_abort_on_error": "false",
            "chunking_max_tokens": str(max_tokens),
            "chunking_include_raw_text": "true",
            "chunking_use_markdown_tables": "true",
            "chunking_tokenizer": (self.embedding_model or "").strip().strip('"').strip("'"),
            "chunking_merge_peers": str(merge_peers).lower(),
            "include_converted_doc": "true",
        }
        if ocr_lang:
            data["convert_ocr_lang"] = list(ocr_lang)
        if describe_pictures and picture_description_prompt:
            data["convert_picture_description_custom_config"] = picture_description_prompt

        try:
            response = await client.post(
                self.chunk_hybrid_file_async_url, files=files, data=data
            )
            response.raise_for_status()
            result = response.json()
            task_id = result.get("task_id")
            if not task_id:
                raise RuntimeError(f"No task_id in Docling response: {result}")
            return task_id
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise RuntimeError(
                f"Cannot reach Docling service at {self.base_url}: {e}"
            ) from e
        except httpx.HTTPStatusError as e:
            raise RuntimeError(
                f"Docling service returned {e.response.status_code}: {e.response.text}"
            ) from e

    async def _wait_for_completion(
        self, client: httpx.AsyncClient, task_id: str
    ) -> None:
        poll_url = f"{self.status_poll_url}/{task_id}"
        deadline = time.monotonic() + (self.max_poll_attempts * self.poll_interval)

        while time.monotonic() < deadline:
            iter_started = time.monotonic()
            try:
                response = await client.get(
                    poll_url, params={"wait": int(self.poll_interval)}
                )
                response.raise_for_status()
                status = (response.json().get("task_status", "") or "").lower()
                if status in ("success", "partial_success", "skipped"):
                    return
                if status == "failure":
                    raise RuntimeError(
                        f"Task {task_id} failed: {response.json().get('task_meta', {})}"
                    )
            except httpx.TimeoutException:
                pass
            except httpx.HTTPStatusError as e:
                if e.response.status_code != 404:
                    raise RuntimeError(
                        f"Error polling task {task_id}: "
                        f"{e.response.status_code} - {e.response.text}"
                    ) from e

            elapsed = time.monotonic() - iter_started
            if elapsed < self.poll_interval:
                await asyncio.sleep(self.poll_interval - elapsed)

        raise RuntimeError(f"Task {task_id} timed out waiting for completion")

    async def _get_result(
        self, client: httpx.AsyncClient, task_id: str
    ) -> ConversionResult:
        response = await client.get(f"{self.result_url}/{task_id}")
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "failure":
            raise RuntimeError(f"Docling conversion failed: {data.get('errors', [])}")

        chunks = self._parse_chunks(data)
        markdown, document = self._parse_document(data)
        return ConversionResult(chunks=chunks, markdown=markdown, document=document)

    @staticmethod
    def _parse_chunks(data: dict) -> list[ChunkResult]:
        raw_chunks = data.get("chunks") or []
        chunks: list[ChunkResult] = []
        for idx, c in enumerate(raw_chunks):
            if not isinstance(c, dict):
                continue
            text = c.get("text") or c.get("raw_text") or ""
            if not text:
                continue
            chunks.append(
                ChunkResult(
                    text=text,
                    chunk_index=c.get("chunk_index", idx),
                    num_tokens=c.get("num_tokens"),
                    headings=c.get("headings") or [],
                    captions=c.get("captions") or [],
                    page_numbers=c.get("page_numbers") or [],
                    metadata=c.get("metadata") or {},
                )
            )
        return chunks

    @staticmethod
    def _parse_document(data: dict) -> tuple[str, dict]:
        """Pull (markdown, document_json) from either the chunk-endpoint shape
        (documents[0].content) or the convert-endpoint shape (document)."""
        markdown = ""
        document: dict = {}

        docs_list = data.get("documents")
        if isinstance(docs_list, list) and docs_list:
            content = docs_list[0].get("content") if isinstance(docs_list[0], dict) else None
            if isinstance(content, dict):
                markdown = content.get("md_content") or content.get("markdown") or ""
                json_content = content.get("json_content")
                if isinstance(json_content, dict):
                    document = json_content

        if not document:
            doc_wrapper = data.get("document")
            if isinstance(doc_wrapper, dict):
                markdown = markdown or doc_wrapper.get("md_content") or ""
                json_content = doc_wrapper.get("json_content")
                if isinstance(json_content, dict):
                    document = json_content

        if not markdown:
            markdown = data.get("md_content") or data.get("markdown") or ""

        return markdown, document
