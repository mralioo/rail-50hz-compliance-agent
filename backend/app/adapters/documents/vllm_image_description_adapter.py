"""VllmImageDescriptionAdapter — Adapter layer (implements the domain's
ImageDescriptionPort using the remote generative LLM's vision capability).

Verified live against the server: the served model (google/gemma-4-31B-it)
accepts image_url content and gives accurate, detailed descriptions of real
extracted schematics/floor plans (e.g. correctly identified room labels
"Rechnerraum"/"Netzersatzraum"/"TK-Raum" on a real Aufstellplan crop).

Parses a plain-text ``DESCRIPTION: ...`` / ``CATEGORY: ...`` two-line format
rather than JSON: tried vLLM's ``guided_json`` first, but this server/model
combination silently ignores it (no error - it just answers in prose, as if
the parameter weren't sent at all), so a rigid delimited format is the
reliable option, not "hope the model wraps valid JSON".
"""
import logging
import re

from app.adapters.documents.vllm_generative_client import VllmGenerativeClient
from app.domain.documents.models import ImageDescription

logger = logging.getLogger(__name__)

# A fixed, corpus-grounded taxonomy (mirrors the folder categories seen
# throughout dataset/raw/project_1 - Übersichtsschema, Aufstellplan,
# Elektroinstallationsplan, Erdungsanlage/Blitzschutz, Kabellageplan,
# Lageplan - plus generic buckets for non-drawing content) rather than
# free-text categorization: a controlled vocabulary is what actually helps
# downstream clustering/filtering, which is the whole point of this layer.
CATEGORIES = [
    "single_line_diagram",  # Übersichtsschema / Netzschema
    "floor_plan",  # Aufstellplan - room/equipment layout
    "electrical_installation_plan",  # Elektroinstallationsplan
    "earthing_lightning_protection",  # Erdungsanlage / Blitzschutz
    "cable_routing_plan",  # Kabellageplan
    "site_plan",  # Lageplan
    "title_block",  # drawing title block / metadata frame
    "table",  # data table, not a drawing
    "logo_letterhead",  # company logo / letterhead, no technical content
    "photo",  # site photograph
    "other",
]

_SYSTEM_PROMPT = (
    "You describe technical drawings from German railway (Deutsche Bahn) "
    "50 Hz power-supply engineering submittals - schematics, electrical "
    "installation plans, earthing/lightning-protection drawings, floor "
    "plans, and title blocks - for a search and clustering system."
)

_USER_PROMPT = (
    "Describe this image in 1-2 concise, factual sentences: what equipment, "
    "rooms, connections, or labels does it show, and what kind of drawing is "
    "it? Preserve any German technical terms you can read.\n\n"
    f"Then classify it into exactly one category from this list: "
    f"{', '.join(CATEGORIES)}.\n\n"
    "Respond in EXACTLY this two-line format, nothing else:\n"
    "DESCRIPTION: <your description>\n"
    "CATEGORY: <one category from the list>"
)

_RESPONSE_RE = re.compile(
    r"DESCRIPTION:\s*(?P<description>.*?)\s*CATEGORY:\s*(?P<category>\S+)",
    re.IGNORECASE | re.DOTALL,
)


def _parse_response(raw: str) -> ImageDescription:
    match = _RESPONSE_RE.search(raw)
    if not match:
        logger.warning("describe_image: unparseable response %r", raw[:200])
        return ImageDescription(description=raw.strip()[:500], category="other")

    description = match.group("description").strip()
    category = match.group("category").strip().strip(".,").lower()
    if category not in CATEGORIES:
        logger.warning("describe_image: model returned unknown category %r", category)
        category = "other"
    return ImageDescription(description=description, category=category)


class VllmImageDescriptionAdapter:
    def __init__(self, client: VllmGenerativeClient) -> None:
        self._client = client

    async def describe_image(self, image_bytes: bytes) -> ImageDescription:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    self._client.text_content(_USER_PROMPT),
                    self._client.image_content(image_bytes),
                ],
            },
        ]
        raw = await self._client.chat(messages, max_tokens=300, temperature=0.0)
        return _parse_response(raw)
