"""Raw project corpus (dataset/raw/<project>/) -> clean, folder-mirrored
Markdown (dataset/clean/<project>/), via Docling.

Two tiers, picked per-file by measured text density rather than a
folder-name whitelist (robust to future projects with different German
category naming):

- Tier 1 (full Docling ML pipeline: layout + table structure) for files
  with real prose - .docx always, .pdf when its `pdftotext` text layer has
  enough real words to be worth the ~15-22s/page CPU-only cost measured on
  this corpus.
- Tier 2 (fast, no ML - just the `pdftotext` text layer plus folder-derived
  metadata) for everything else - measured on this corpus's CAD-plan/
  calc-report PDFs (Aufstellplan, Erdungsanlage, Stromberdarfberechnung,
  etc.): as little as 87 extracted characters, title-block fragments only,
  the same near-empty result the full ML pipeline produces on them at
  ~1000x the CPU cost.

.zip (redundant archives) and .heic (site photos, no extractable text) are
skipped outright - see `classify()`.

Every output .md carries a YAML frontmatter block (project/substation/
category/source_path/tier/page_count) that `app.kb.project_corpus` reads
as the single source of truth for chunking into OpenSearch/Neo4j.
"""
import json
import re
import subprocess
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

PDFTOTEXT_TIMEOUT_S = 60
TIER1_MIN_WORDS = 50  # below this, a PDF's text layer is title-block noise, not prose
_WORD_RE = re.compile(r"\w{3,}", re.UNICODE)

# Path segments that name a substation in this corpus's folder convention
# (e.g. "ESTW-A Dörstewitz", "ESTW_A Massetal", "ESTW-UZ Erfurt") - matched
# against every path segment, first hit wins.
_SUBSTATION_RE = re.compile(r"^(ESTW|UZ)[\s_-]", re.IGNORECASE)


class Tier(Enum):
    FULL = 1  # Docling ML pipeline
    FAST = 2  # pdftotext-only stub
    SKIPPED = 0


@dataclass
class ManifestEntry:
    source_path: str
    output_path: str | None
    tier: int
    status: str  # "ok" | "skipped" | "error"
    reason: str | None = None


def _pdftotext(path: Path) -> str:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path), "-"],
            capture_output=True,
            text=True,
            timeout=PDFTOTEXT_TIMEOUT_S,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""


def classify(path: Path) -> tuple[Tier, str | None, str]:
    """Returns (tier, skip_reason, pdftotext_text) - text is "" unless a
    .pdf was actually read (avoids a wasted subprocess call for skips/docx)."""
    suffix = path.suffix.lower()
    if suffix == ".zip":
        return Tier.SKIPPED, "redundant archive", ""
    if suffix == ".heic":
        return Tier.SKIPPED, "image, no extractable text", ""
    if suffix == ".docx":
        return Tier.FULL, None, ""
    if suffix != ".pdf":
        return Tier.SKIPPED, f"unsupported file type: {suffix}", ""
    text = _pdftotext(path)
    if len(_WORD_RE.findall(text)) >= TIER1_MIN_WORDS:
        return Tier.FULL, None, text
    return Tier.FAST, None, text


def _substation_for(rel_parts: tuple[str, ...]) -> str | None:
    for part in rel_parts:
        if _SUBSTATION_RE.match(part):
            return part
    return None


def _yaml_str(value: str) -> str:
    """Minimal YAML double-quoted scalar - avoids a PyYAML dependency for
    both writing here and parsing in app.kb.project_corpus (a hand-rolled
    parser matching this exact escaping, not a general YAML reader)."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _frontmatter(
    project: str, rel_path: Path, tier: Tier, page_count: int | None
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
        "---",
        "",
    ]
    return "\n".join(lines)


def convert_tier1(path: Path, project: str, rel_path: Path, out_path: Path) -> int:
    """Full Docling conversion. Returns page count (0 if unknown, e.g. docx)."""
    result = _CONVERTER.convert(str(path))
    page_count = result.document.num_pages() if hasattr(result.document, "num_pages") else 0
    md = result.document.export_to_markdown()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_frontmatter(project, rel_path, Tier.FULL, page_count or None) + md)
    return page_count


def convert_tier2(path: Path, project: str, rel_path: Path, out_path: Path, text: str) -> None:
    body = text.strip() or "(no extractable text - title-block/drawing only, see original PDF)"
    md = (
        _frontmatter(project, rel_path, Tier.FAST, None)
        + f"# {path.name}\n\n"
        + "```\n"
        + body
        + "\n```\n"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md)


class _LazyConverter:
    """Docling's DocumentConverter loads its ML models on first use (several
    seconds) - built once per process and reused across every Tier-1 file in
    a run instead of once per file."""

    _instance = None

    def convert(self, path: str):
        if self._instance is None:
            from docling.document_converter import DocumentConverter

            self._instance = DocumentConverter()
        return self._instance.convert(path)


_CONVERTER = _LazyConverter()


def run(
    raw_dir: Path, clean_dir: Path, project: str, force: bool = False, limit: int | None = None
) -> list[ManifestEntry]:
    project_raw = raw_dir / project
    project_clean = clean_dir / project
    manifest: list[ManifestEntry] = []
    n_converted = 0

    for path in sorted(project_raw.rglob("*")):
        if not path.is_file():
            continue
        rel_path = path.relative_to(project_raw)
        out_path = project_clean / rel_path.with_suffix(".md")

        tier, skip_reason, text = classify(path)
        if tier is Tier.SKIPPED:
            manifest.append(
                ManifestEntry(str(rel_path), None, 0, "skipped", skip_reason)
            )
            continue

        if limit is not None and n_converted >= limit:
            manifest.append(
                ManifestEntry(str(rel_path), None, tier.value, "skipped", "over --limit")
            )
            continue

        if out_path.exists() and not force and out_path.stat().st_mtime >= path.stat().st_mtime:
            manifest.append(
                ManifestEntry(str(rel_path), str(out_path), tier.value, "ok", "cached")
            )
            n_converted += 1
            continue

        try:
            if tier is Tier.FULL:
                convert_tier1(path, project, rel_path, out_path)
            else:
                convert_tier2(path, project, rel_path, out_path, text)
            manifest.append(
                ManifestEntry(str(rel_path), str(out_path), tier.value, "ok")
            )
        except Exception as exc:  # noqa: BLE001 - one bad file must not kill the batch
            manifest.append(
                ManifestEntry(str(rel_path), None, tier.value, "error", str(exc))
            )
        n_converted += 1

    project_clean.mkdir(parents=True, exist_ok=True)
    manifest_path = project_clean / "_manifest.json"
    manifest_path.write_text(
        json.dumps([asdict(m) for m in manifest], indent=2, ensure_ascii=False)
    )
    return manifest
