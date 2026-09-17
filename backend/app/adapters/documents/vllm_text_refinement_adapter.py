"""VllmTextRefinementAdapter — Adapter layer (implements the domain's
TextRefinementPort using the remote generative LLM).

Cleans OCR/extraction artifacts out of already-extracted Docling text:
repeated characters/lines, broken line-wraps, stray whitespace — without
altering technical meaning. Not a summarizer; the prompt explicitly forbids
shortening, translating, or adding commentary.
"""
import logging

from app.adapters.documents.vllm_generative_client import VllmGenerativeClient

logger = logging.getLogger(__name__)

# Above this, a single document's raw text risks an unreasonably slow/expensive
# LLM call even though the model's 131k-token context could technically fit
# it (the one measured outlier in this corpus was ~242k chars / ~60k tokens,
# comfortably inside that budget) - truncate defensively rather than let one
# oversized document stall a whole batch run. A documented lossy tradeoff,
# same pattern as opensearch_store.py's _VLLM_MAX_CHARS.
_MAX_INPUT_CHARS = 120_000

_SYSTEM_PROMPT = (
    "You are a meticulous text-cleanup assistant for German railway "
    "engineering documents (Deutsche Bahn 50 Hz power-supply submittals), "
    "extracted from PDFs/DOCX via OCR and automated layout analysis. You fix "
    "extraction artifacts without changing technical meaning."
)

_USER_PROMPT_TEMPLATE = """Clean the following extracted document text.

Fix:
- OCR noise (garbled characters, misrecognized symbols)
- Exact character/word/line repetitions introduced by extraction artifacts
- Broken line-wraps and stray/duplicated whitespace
- Obviously duplicated headers/footers repeated across pages

Do NOT:
- Summarize, shorten, or omit any real technical content (part numbers, \
measurements, German technical terms, table data, drawing references)
- Translate anything
- Add commentary, explanations, or notes about what you changed
- Invent content that isn't in the source

Output ONLY the cleaned text, nothing else — no preamble, no code fences.

---
{text}
---
"""


class VllmTextRefinementAdapter:
    def __init__(self, client: VllmGenerativeClient) -> None:
        self._client = client

    async def refine_text(self, raw_text: str) -> str:
        if not raw_text or not raw_text.strip():
            return raw_text

        text = raw_text
        if len(text) > _MAX_INPUT_CHARS:
            logger.warning(
                "refine_text: input %d chars exceeds %d, truncating before cleanup",
                len(text),
                _MAX_INPUT_CHARS,
            )
            text = text[:_MAX_INPUT_CHARS]

        # Cleaned output is roughly the same length as the input (this is
        # cleanup, not compression) - size the budget accordingly, plus margin.
        max_tokens = min(16384, max(1024, len(text) // 2))

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(text=text)},
        ]
        cleaned = await self._client.chat(messages, max_tokens=max_tokens, temperature=0.0)
        cleaned = cleaned.strip()
        return cleaned or raw_text
