"""IoC composition root.

The one place that knows about concrete adapters and wires them to the
domain ports they implement. Application/API code asks bootstrap for a
port implementation by name/config; it never imports an adapter class
directly. Grows one bounded context at a time as the migration in
docs/architecture/MIGRATION_MAP.md proceeds - wires `cad` and `documents`.
"""
from pathlib import Path

from app.adapters.cad.acadsharp_adapter import AcadSharpEngine
from app.adapters.cad.ezdxf_adapter import EzdxfEngine
from app.adapters.cad.libredwg_adapter import LibreDwgEngine
from app.adapters.cad.qcad_adapter import QCadEngine
from app.domain.cad.ports import CadEnginePort

CAD_ENGINES: dict[str, CadEnginePort] = {
    "ezdxf": EzdxfEngine(),
    "libredwg": LibreDwgEngine(),
    "acadsharp": AcadSharpEngine(),
    "qcad": QCadEngine(),
}


def get_cad_engine(name: str) -> CadEnginePort:
    try:
        return CAD_ENGINES[name]
    except KeyError:
        raise KeyError(f"Unknown CAD engine '{name}', available: {list(CAD_ENGINES)}") from None


# ── documents (Docling extraction) ──────────────────────────────────────────
# Only one implementation exists per port today (no swapping yet), so these
# are factories rather than a name-keyed registry like CAD_ENGINES above —
# still the single place that knows the concrete adapter classes.


def get_docling_client(base_url: str | None = None):
    from app.adapters.documents.docling_client import DoclingClient

    return DoclingClient(base_url=base_url)


def get_document_conversion_client(
    base_url: str | None = None,
    *,
    force_ocr: bool = False,
    images_scale: float | None = None,
    describe_pictures: bool = False,
):
    from app.adapters.documents.docling_conversion_adapter import DoclingConversionAdapter

    return DoclingConversionAdapter(
        client=get_docling_client(base_url),
        force_ocr=force_ocr,
        images_scale=images_scale,
        describe_pictures=describe_pictures,
    )


def get_document_text_extraction_client(base_url: str | None = None):
    from app.adapters.documents.docling_text_extraction_adapter import (
        DoclingTextExtractionAdapter,
    )

    return DoclingTextExtractionAdapter(client=get_docling_client(base_url))


def get_document_file_storage(root: Path):
    """Local-filesystem artifact store rooted at *root* (e.g.
    ``dataset/clean/<project>``). Swap for an S3/Garage-backed adapter here
    when one is deployed — no change needed above this function."""
    from app.adapters.documents.local_file_storage_adapter import LocalFileStorageAdapter

    return LocalFileStorageAdapter(root=root)


# ── documents refinement (LLM cleanup + image description) ──────────────────
# dataset/clean/<project> -> dataset/super_clean/<project>. Same remote
# server as Docling/embeddings (nginx-proxied at /generative/).


def get_generative_client(base_url: str | None = None):
    from app.adapters.documents.vllm_generative_client import VllmGenerativeClient

    return VllmGenerativeClient(base_url=base_url)


def get_text_refinement_client(base_url: str | None = None):
    from app.adapters.documents.vllm_text_refinement_adapter import VllmTextRefinementAdapter

    return VllmTextRefinementAdapter(client=get_generative_client(base_url))


def get_image_description_client(base_url: str | None = None):
    from app.adapters.documents.vllm_image_description_adapter import VllmImageDescriptionAdapter

    return VllmImageDescriptionAdapter(client=get_generative_client(base_url))
