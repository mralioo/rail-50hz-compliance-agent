"""Raw project corpus (dataset/raw/<project>/) -> clean, folder-mirrored
Markdown + extracted images (dataset/clean/<project>/), via the **Docling
server** (not a local CPU pipeline).

Every convertible file (.pdf, .docx) is sent to the Docling service
(``DOCLING_BASE_URL``) with image export enabled - the same async API +
polling mechanism the ITUKI backend uses. One call returns the hybrid-chunked
text, the full Markdown, and the converted-document JSON; individual pictures
are cropped out of the server's full-page renders (see ``docling_images``).

This corpus is AEC data - German railway 50 Hz submittals: PDFs of schematics,
electrical plans (Übersichtsschema, Elektroinstallationsplan), earthing and
lightning-protection drawings, current-demand calculations. So the extraction
is tuned for it:

- German OCR (``de``+``en``) so drawing labels and title-block text on
  scanned/vector plans are read, not dropped.
- ``images_scale=2.0`` full-page renders so cropped schematics stay legible.
- picture classification on, so each extracted image carries a predicted type.
- ``force_ocr`` and per-picture VLM description available as opt-in flags for
  runs that need to pull text off image-only drawings or narrate each plan.

Output per source file:
- ``<mirror>.md``  - YAML frontmatter (project/substation/category/
  source_path/tier/page_count/image_count) + Markdown with each
  ``<!-- image -->`` placeholder replaced, in document order, by a link to
  the saved crop, followed by an "Extracted images" reference table.
- ``<mirror>/images/NNN_pPP_<sha8>.png`` - one PNG per picture, numbered in
  document order.

The frontmatter schema is the contract read by ``app.kb.project_corpus`` -
keep it in sync with that module's hand-rolled parser.

.zip (redundant archives) and .heic (site photos) are skipped - see
``classify``.
"""
import asyncio
import json
import re
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from app.core.config import get_settings
from app.ingestion.docling_client import ConversionResult, DoclingClient
from app.ingestion.docling_images import ExtractedImage, extract_images

# Path segments naming a substation in this corpus's folder convention
# (e.g. "ESTW-A Dörstewitz", "ESTW_A Massetal", "ESTW-UZ Erfurt").
_SUBSTATION_RE = re.compile(r"^(ESTW|UZ)[\s_-]", re.IGNORECASE)
_IMAGE_PLACEHOLDER_RE = re.compile(r"<!--\s*image\s*-->", re.IGNORECASE)

# German railway electrical-engineering document. Used only when picture
# description is switched on (--describe-pictures); guides the server-side VLM.
AEC_PICTURE_PROMPT = (
    "This is a technical drawing from a German railway (Deutsche Bahn) 50 Hz "
    "power-supply submittal - a schematic, electrical installation plan, "
    "earthing or lightning-protection drawing, or a single-line diagram. "
    "Describe the depicted equipment, connections, labels and reference "
    "designators concisely and factually. Preserve German technical terms."
)


class Tier(Enum):
    FULL = 1  # Docling server conversion
    SKIPPED = 0


@dataclass
class ManifestEntry:
    source_path: str
    output_path: str | None
    tier: int
    status: str  # "ok" | "skipped" | "error"
    page_count: int | None = None
    image_count: int = 0
    reason: str | None = None


def classify(path: Path) -> tuple[Tier, str | None]:
    """(tier, skip_reason). Only decides whether to send the file to the
    server - the server runs the full ML pipeline on everything it gets."""
    suffix = path.suffix.lower()
    if suffix == ".zip":
        return Tier.SKIPPED, "redundant archive"
    if suffix == ".heic":
        return Tier.SKIPPED, "image, no extractable text"
    if suffix in (".pdf", ".docx"):
        return Tier.FULL, None
    return Tier.SKIPPED, f"unsupported file type: {suffix}"


def _substation_for(rel_parts: tuple[str, ...]) -> str | None:
    for part in rel_parts:
        if _SUBSTATION_RE.match(part):
            return part
    return None


def _yaml_str(value: str) -> str:
    """Minimal YAML double-quoted scalar - matches the hand-rolled parser in
    app.kb.project_corpus (no PyYAML dependency on either side)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _frontmatter(
    project: str,
    rel_path: Path,
    tier: Tier,
    page_count: int | None,
    image_count: int,
) -> str:
    rel_parts = rel_path.parts
    category = rel_path.parent.name if len(rel_parts) > 1 else ""
    substation = _substation_for(rel_parts) or ""
    lines = [
        "---",
        f"project: {_yaml_str(project)}",
        f"substation: {_yaml_str(substation)}",
        f"category: {_yaml_str(category)}",
        f"source_path: {_yaml_str((Path('dataset/raw') / project / rel_path).as_posix())}",
        f"tier: {tier.value}",
        f"page_count: {page_count if page_count is not None else 'null'}",
        f"image_count: {image_count}",
        "---",
        "",
    ]
    return "\n".join(lines)


def _image_filename(img: ExtractedImage) -> str:
    page = f"p{img.page_number:03d}" if img.page_number is not None else "pXXX"
    return f"{img.position_index:03d}_{page}_{img.checksum[:8]}.png"


def _inline_image_links(markdown: str, saved: dict[int, str]) -> str:
    """Replace each ``<!-- image -->`` placeholder, in order, with a link to
    the correspondingly-ordered saved crop.

    Docling emits one placeholder per picture in document order, so the k-th
    placeholder is picture index k. A picture skipped during cropping (too
    small / no bbox) has no saved file, so its placeholder is annotated
    instead of dropped, keeping the k -> picture-index alignment intact.
    """
    counter = {"i": -1}

    def repl(_m: re.Match) -> str:
        counter["i"] += 1
        rel = saved.get(counter["i"])
        if rel is None:
            return "<!-- image (not extracted: too small or no bbox) -->"
        return f"![picture {counter['i']}]({rel})"

    return _IMAGE_PLACEHOLDER_RE.sub(repl, markdown)


def _images_reference_table(images: list[ExtractedImage], rel_dir: str) -> str:
    if not images:
        return ""
    lines = [
        "",
        "## Extracted images",
        "",
        "| # | page | file | type | caption |",
        "| - | ---- | ---- | ---- | ------- |",
    ]
    for img in images:
        fname = _image_filename(img)
        page = img.page_number if img.page_number is not None else ""
        cls = img.classification or ""
        cap = (img.caption or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {img.position_index} | {page} | "
            f"[{fname}]({rel_dir}/{fname}) | {cls} | {cap} |"
        )
    lines.append("")
    return "\n".join(lines)


def _write_outputs(
    result: ConversionResult,
    images: list[ExtractedImage],
    project: str,
    rel_path: Path,
    out_path: Path,
    page_count: int | None,
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    saved: dict[int, str] = {}
    if images:
        img_dir = out_path.with_suffix("")  # <mirror>/images sits next to <mirror>.md
        images_subdir = img_dir / "images"
        images_subdir.mkdir(parents=True, exist_ok=True)
        rel_dir = f"{out_path.stem}/images"
        for img in images:
            fname = _image_filename(img)
            (images_subdir / fname).write_bytes(img.data)
            saved[img.position_index] = f"{rel_dir}/{fname}"

    body = result.markdown or ""
    if saved:
        body = _inline_image_links(body, saved)
    body += _images_reference_table(images, f"{out_path.stem}/images")

    out_path.write_text(
        _frontmatter(project, rel_path, Tier.FULL, page_count, len(images)) + body
    )


async def _convert_one(
    client: DoclingClient,
    path: Path,
    *,
    force_ocr: bool,
    images_scale: float,
    describe_pictures: bool,
) -> tuple[ConversionResult, list[ExtractedImage], int | None]:
    file_bytes = path.read_bytes()
    result = await client.chunk_file_with_images(
        file_bytes=file_bytes,
        filename=path.name,
        force_ocr=force_ocr,
        ocr_lang=["de", "en"],
        images_scale=images_scale,
        classify_pictures=True,
        describe_pictures=describe_pictures,
        picture_description_prompt=AEC_PICTURE_PROMPT if describe_pictures else None,
    )
    images = extract_images(result.document)
    pages = result.document.get("pages") if result.document else None
    page_count = len(pages) if isinstance(pages, dict) and pages else None
    return result, images, page_count


async def run(
    raw_dir: Path,
    clean_dir: Path,
    project: str,
    *,
    force: bool = False,
    limit: int | None = None,
    base_url: str | None = None,
    force_ocr: bool = False,
    images_scale: float | None = None,
    describe_pictures: bool = False,
) -> list[ManifestEntry]:
    settings = get_settings()
    project_raw = raw_dir / project
    project_clean = clean_dir / project
    manifest: list[ManifestEntry] = []
    n_converted = 0

    if images_scale is None:
        images_scale = settings.docling_images_scale
    client = DoclingClient(
        base_url=base_url or settings.docling_base_url,
        embedding_model=settings.embedding_model,
    )

    for path in sorted(project_raw.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(project_raw)
        out_path = project_clean / rel_path.with_suffix(".md")

        tier, skip_reason = classify(path)
        if tier is Tier.SKIPPED:
            manifest.append(ManifestEntry(str(rel_path), None, 0, "skipped", reason=skip_reason))
            continue

        if limit is not None and n_converted >= limit:
            manifest.append(
                ManifestEntry(str(rel_path), None, tier.value, "skipped", reason="over --limit")
            )
            continue

        if out_path.exists() and not force and out_path.stat().st_mtime >= path.stat().st_mtime:
            manifest.append(
                ManifestEntry(str(rel_path), str(out_path), tier.value, "ok", reason="cached")
            )
            n_converted += 1
            continue

        try:
            result, images, page_count = await _convert_one(
                client,
                path,
                force_ocr=force_ocr,
                images_scale=images_scale,
                describe_pictures=describe_pictures,
            )
            _write_outputs(result, images, project, rel_path, out_path, page_count)
            manifest.append(
                ManifestEntry(
                    str(rel_path),
                    str(out_path),
                    tier.value,
                    "ok",
                    page_count=page_count,
                    image_count=len(images),
                )
            )
        except Exception as exc:  # noqa: BLE001 - one bad file must not kill the batch
            manifest.append(
                ManifestEntry(str(rel_path), None, tier.value, "error", reason=str(exc))
            )
        n_converted += 1

    project_clean.mkdir(parents=True, exist_ok=True)
    (project_clean / "_manifest.json").write_text(
        json.dumps([asdict(m) for m in manifest], indent=2, ensure_ascii=False)
    )
    return manifest


def run_sync(*args, **kwargs) -> list[ManifestEntry]:
    """Blocking wrapper around :func:`run` for CLI/script callers."""
    return asyncio.run(run(*args, **kwargs))
