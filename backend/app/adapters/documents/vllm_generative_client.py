"""VllmGenerativeClient — Adapter layer.

Low-level HTTP client for the remote generative LLM (nginx-proxied at
``/generative/``, same server as Docling and the embedding model — see
``docling_client.py`` and ``opensearch_store.py``'s ``vllm`` embedding
provider). OpenAI-compatible ``/v1/chat/completions``; supports both plain
text and vision (image_url) messages since the served model
(``google/gemma-4-31B-it`` at the time of writing) is multimodal — verified
directly against the live server.

Used by the refinement layer's text-cleanup and image-description adapters
(see ``vllm_text_refinement_adapter.py`` / ``vllm_image_description_adapter.py``).
"""
import base64
import json
import logging

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class VllmGenerativeClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        *,
        timeout: float = 300.0,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.vllm_generative_base_url).rstrip("/")
        self.model = model or settings.generative_model
        self.timeout = timeout
        self._url = f"{self.base_url}/v1/chat/completions"

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/v1/models")
                return response.status_code == 200
        except httpx.HTTPError:
            return False

    @staticmethod
    def image_content(image_bytes: bytes, mime_type: str = "image/png") -> dict:
        """Build an OpenAI-style ``image_url`` content part from raw bytes."""
        encoded = base64.b64encode(image_bytes).decode("ascii")
        return {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}}

    @staticmethod
    def text_content(text: str) -> dict:
        return {"type": "text", "text": text}

    async def chat(
        self,
        messages: list[dict],
        *,
        max_tokens: int = 2048,
        temperature: float = 0.0,
        guided_json: dict | None = None,
    ) -> str:
        """Send a chat completion request, return the assistant's text content.

        ``guided_json`` (a JSON Schema dict), when given, is passed through as
        vLLM's guided-decoding parameter of the same name. **Verified this
        server/model combination (google/gemma-4-31B-it) silently ignores
        it** — no error, the response just comes back as ordinary prose, not
        JSON — so callers should not rely on it for correctness; the
        image-description adapter parses a plain delimited text format
        instead for exactly this reason. Left as a passthrough in case a
        future server/model actually honors it.
        """
        payload: dict = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if guided_json is not None:
            payload["guided_json"] = guided_json

        timeout = httpx.Timeout(connect=30.0, read=self.timeout, write=60.0, pool=30.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(self._url, json=payload)
                response.raise_for_status()
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                raise RuntimeError(f"Cannot reach generative service at {self.base_url}: {e}") from e
            except httpx.HTTPStatusError as e:
                raise RuntimeError(
                    f"Generative service returned {e.response.status_code}: {e.response.text}"
                ) from e

        data = response.json()
        try:
            return data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError) as e:
            raise RuntimeError(f"Unexpected generative response shape: {json.dumps(data)[:500]}") from e
