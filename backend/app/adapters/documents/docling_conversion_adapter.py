"""
DoclingConversionAdapter — Adapter layer (implements the domain's
DocumentConversionClientPort).

Uses a single Docling API call that
returns both semantically-chunked text and embedded images. This eliminates
the double-conversion penalty of calling separate chunking and image-
extraction endpoints.

Tuned for this project's corpus: German DB railway 50 Hz submittals — PDFs of
schematics, electrical plans, earthing/lightning-protection drawings, current-
demand calculations. So German OCR (``de``+``en``) and picture classification
are on by default, and page renders are captured at 2x scale so cropped
schematics stay legible.
"""

import base64
import hashlib
import io
import logging
from uuid import uuid4

from PIL import Image

from app.adapters.documents.docling_client import ChunkResult, DoclingClient
from app.domain.documents.models import Chunk, ExtractedImage

logger = logging.getLogger(__name__)

# Skip images smaller than this (likely decorative or a crop artifact)
_MIN_IMAGE_BYTES = 512

# German railway electrical-engineering document. Used only when picture
# description is switched on; guides the server-side VLM if configured.
AEC_PICTURE_PROMPT = (
    "This is a technical drawing from a German railway (Deutsche Bahn) 50 Hz "
    "power-supply submittal - a schematic, electrical installation plan, "
    "earthing or lightning-protection drawing, or a single-line diagram. "
    "Describe the depicted equipment, connections, labels and reference "
    "designators concisely and factually. Preserve German technical terms."
)


class DoclingConversionAdapter:
    """
    Single-pass document conversion: text chunks + extracted images.

    Calls ``DoclingClient.chunk_file_with_images()`` which submits the document
    to Docling's hybrid chunker with image extraction enabled. The response
    contains both the chunk list and the full converted document JSON with
    full-page renders.

    Images are extracted by cropping individual picture bounding boxes from the
    page render images that Docling provides in ``document.pages[N].image.uri``
    (base64 PNG). Bounding boxes come from ``pictures[i].prov[0].bbox`` with
    ``coord_origin=BOTTOMLEFT``; they are converted to PIL (top-left)
    coordinates before cropping.

    This approach works for all document formats Docling supports (PDF, DOCX,
    PPTX, etc.).
    """

    def __init__(
        self,
        client: DoclingClient,
        max_tokens: int = 512,
        force_ocr: bool = False,
        ocr_lang: list[str] | None = None,
        images_scale: float | None = None,
        classify_pictures: bool = True,
        describe_pictures: bool = False,
        merge_peers: bool = True,
    ) -> None:
        self._client = client
        self._max_tokens = max_tokens
        self._force_ocr = force_ocr
        self._ocr_lang = ocr_lang or ["de", "en"]
        self._images_scale = images_scale
        self._classify_pictures = classify_pictures
        self._describe_pictures = describe_pictures
        self._merge_peers = merge_peers

    async def convert_document(
        self,
        file_bytes: bytes,
        filename: str,
    ) -> tuple[list[Chunk], list[ExtractedImage]]:
        """
        Convert a document, returning text chunks and extracted images.

        Text chunks come from Docling's hybrid chunker. Images are cropped
        from full-page renders returned by the Docling server, using bounding
        boxes from picture provenance metadata.

        Args:
            file_bytes: Raw document bytes (PDF, DOCX, PPTX, etc.)
            filename: Original filename — used to determine file type.

        Returns:
            Tuple of (text_chunks, images).
        """
        logger.info(
            "Converting document '%s' (%d bytes) with image extraction",
            filename,
            len(file_bytes),
        )

        chunk_results, document = await self._client.chunk_file_with_images(
            file_bytes=file_bytes,
            filename=filename,
            max_tokens=self._max_tokens,
            force_ocr=self._force_ocr,
            ocr_lang=self._ocr_lang,
            images_scale=self._images_scale,
            classify_pictures=self._classify_pictures,
            describe_pictures=self._describe_pictures,
            picture_description_prompt=AEC_PICTURE_PROMPT
            if self._describe_pictures
            else None,
            merge_peers=self._merge_peers,
        )

        text_chunks = self._parse_chunks(chunk_results)
        images = self._extract_images_from_page_renders(document)

        logger.info(
            "Conversion complete: %d text chunks, %d image(s) for '%s'",
            len(text_chunks),
            len(images),
            filename,
        )
        return text_chunks, images

    # ---- private helpers ----

    def _extract_images_from_page_renders(self, document: dict) -> list[ExtractedImage]:
        """
        Crop individual images from Docling full-page renders.

        Docling does not embed per-picture bytes even when
        ``image_export_mode=embedded`` is requested. Instead, it provides:
          - ``document.pages[page_no].image.uri``  — full-page render (base64 PNG)
          - ``document.pictures[i].prov[0].bbox``  — bounding box (BOTTOMLEFT coords)
          - ``document.pages[page_no].size``        — page dimensions in document units

        This method decodes the page render, converts the BOTTOMLEFT bbox to
        PIL (top-left) pixel coordinates, and crops each picture from the
        render. Pictures are returned in Docling document order
        (``position_index``) — this order matters for this corpus since it
        carries meaning (sheet layout, legend, detail views) and is what the
        extracted-text artifact's inline ``<!-- image -->`` placeholders are
        matched against.
        """
        if not document:
            return []

        pictures = self._find_pictures(document)
        if not pictures:
            return []

        pages_dict = document.get("pages") or {}
        # Cache decoded page renders: page_no (int) → PIL Image
        page_renders: dict[int, Image.Image] = {}

        images: list[ExtractedImage] = []
        for idx, pic in enumerate(pictures):
            prov_list = pic.get("prov") or []
            if not prov_list:
                logger.debug("Skipping picture [%d]: no provenance", idx)
                continue

            prov = prov_list[0]
            page_no = prov.get("page_no") or prov.get("page_number")
            if page_no is None:
                logger.debug("Skipping picture [%d]: no page_no in provenance", idx)
                continue

            bbox = prov.get("bbox")
            if not isinstance(bbox, dict):
                logger.debug("Skipping picture [%d]: no bbox", idx)
                continue

            # Decode page render (cached)
            if page_no not in page_renders:
                page_img = self._decode_page_render(pages_dict, page_no)
                if page_img is None:
                    logger.debug(
                        "Skipping picture [%d]: page %d render unavailable",
                        idx,
                        page_no,
                    )
                    continue
                page_renders[page_no] = page_img
            page_img = page_renders[page_no]

            # Get page document-space size for coordinate conversion
            page_size = self._get_page_size(pages_dict, page_no)
            crop_box = self._bbox_to_pil_crop(bbox, page_img.size, page_size)
            if crop_box is None:
                logger.debug("Skipping picture [%d]: invalid crop box", idx)
                continue

            try:
                cropped = page_img.crop(crop_box)
            except Exception:
                logger.debug("Skipping picture [%d]: crop failed", idx, exc_info=True)
                continue

            img_bytes = self._image_to_png_bytes(cropped)
            if len(img_bytes) < _MIN_IMAGE_BYTES:
                logger.debug(
                    "Skipping picture [%d]: cropped image too small (%d bytes)",
                    idx,
                    len(img_bytes),
                )
                continue

            checksum = hashlib.sha256(img_bytes).hexdigest()
            images.append(
                ExtractedImage(
                    id=str(uuid4()),
                    document_id="",  # set by ConvertDocumentStep
                    data=img_bytes,
                    mime_type="image/png",
                    checksum=checksum,
                    position_index=idx,
                    page_number=page_no,
                    bounding_box=bbox,
                    caption=self._first_caption(pic),
                    classification=self._classification(pic),
                    width=cropped.width,
                    height=cropped.height,
                    size_bytes=len(img_bytes),
                )
            )
            logger.info(
                "Extracted image [%d]: page=%d crop=%s size=%d bytes",
                idx,
                page_no,
                crop_box,
                len(img_bytes),
            )

        logger.info(
            "_extract_images_from_page_renders: extracted %d / %d picture(s)",
            len(images),
            len(pictures),
        )
        return images

    @staticmethod
    def _first_caption(pic: dict) -> str | None:
        captions = pic.get("captions") or []
        if captions and isinstance(captions, list):
            first = captions[0]
            return first.get("text") if isinstance(first, dict) else str(first)
        return None

    @staticmethod
    def _classification(pic: dict) -> str | None:
        """Best predicted picture class, when picture-classification was on."""
        for ann in pic.get("annotations") or []:
            if not isinstance(ann, dict):
                continue
            classes = ann.get("predicted_classes") or ann.get("predicted_class")
            if isinstance(classes, list) and classes:
                top = classes[0]
                return top.get("class_name") or top.get("label") if isinstance(top, dict) else str(top)
            if isinstance(classes, str):
                return classes
        return None

    def _decode_page_render(
        self, pages_dict: dict, page_no: int
    ) -> "Image.Image | None":
        """Decode a full-page render from Docling's pages dict."""
        page = pages_dict.get(str(page_no)) or pages_dict.get(page_no)
        if not isinstance(page, dict):
            return None
        image_info = page.get("image")
        if not isinstance(image_info, dict):
            return None
        uri = image_info.get("uri") or image_info.get("url")
        if not isinstance(uri, str):
            return None

        try:
            if uri.startswith("data:"):
                # data:<mime>;base64,<data>
                _, encoded = uri.split(",", 1)
                img_bytes = base64.b64decode(encoded)
            else:
                img_bytes = base64.b64decode(uri)
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        except Exception:
            logger.debug("Failed to decode page %d render", page_no, exc_info=True)
            return None

    def _get_page_size(
        self, pages_dict: dict, page_no: int
    ) -> tuple[float, float] | None:
        """Return (width, height) in document units from pages_dict, or None."""
        page = pages_dict.get(str(page_no)) or pages_dict.get(page_no)
        if not isinstance(page, dict):
            return None
        size = page.get("size")
        if isinstance(size, dict):
            w = size.get("width")
            h = size.get("height")
            if w and h:
                return float(w), float(h)
        return None

    def _bbox_to_pil_crop(
        self,
        bbox: dict,
        img_size: tuple[int, int],
        page_size: tuple[float, float] | None,
    ) -> tuple[int, int, int, int] | None:
        """
        Convert a Docling BOTTOMLEFT bounding box to a PIL crop tuple.

        Docling bbox keys: l (left), b (bottom), r (right), t (top)
        coord_origin: BOTTOMLEFT → y=0 at bottom, y increases upward.

        PIL crop: (left, top, right, bottom) where (0,0) is top-left.

        Conversion (page_height H in doc units, image height H_px):
            scale_x = img_width  / page_width
            scale_y = img_height / page_height
            PIL_left   = l * scale_x
            PIL_top    = (H - t) * scale_y
            PIL_right  = r * scale_x
            PIL_bottom = (H - b) * scale_y
        """
        x_left = bbox.get("l")
        y_bottom = bbox.get("b")
        x_right = bbox.get("r")
        y_top = bbox.get("t")
        if x_left is None or y_bottom is None or x_right is None or y_top is None:
            return None

        bl: float = float(x_left)
        bb: float = float(y_bottom)
        br: float = float(x_right)
        bt: float = float(y_top)

        img_w, img_h = img_size

        if page_size:
            page_w, page_h = page_size
            scale_x = img_w / page_w
            scale_y = img_h / page_h
        else:
            # Assume 1pt = 1px (unlikely but safe fallback)
            scale_x = 1.0
            scale_y = 1.0
            page_h = float(img_h)

        left = int(bl * scale_x)
        top = int((page_h - bt) * scale_y)
        right = int(br * scale_x)
        bottom = int((page_h - bb) * scale_y)

        # Clamp to image bounds
        left = max(0, min(left, img_w))
        top = max(0, min(top, img_h))
        right = max(0, min(right, img_w))
        bottom = max(0, min(bottom, img_h))

        if right <= left or bottom <= top:
            return None

        return (left, top, right, bottom)

    @staticmethod
    def _image_to_png_bytes(img: "Image.Image") -> bytes:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        return buf.getvalue()

    def _parse_chunks(self, chunk_results: list[ChunkResult]) -> list[Chunk]:
        return [
            Chunk(
                id=str(uuid4()),
                document_id="",  # set to real document_id by ConvertDocumentStep
                text=cr.text,
                index=cr.chunk_index,
                metadata={
                    **({"page_numbers": cr.page_numbers} if cr.page_numbers else {}),
                    **({"headings": cr.headings} if cr.headings else {}),
                    **({"captions": cr.captions} if cr.captions else {}),
                },
            )
            for cr in chunk_results
            if cr.text
        ]

    def _find_pictures(self, document: dict) -> list[dict]:
        """Try common Docling response field names for image lists."""
        for field_name in ("pictures", "figures", "images"):
            value = document.get(field_name)
            if isinstance(value, list) and value:
                logger.info(
                    "Found %d picture(s) under document.%s",
                    len(value),
                    field_name,
                )
                return value
        logger.warning(
            "_find_pictures: no pictures found. Searched: pictures, figures, images. "
            "Document top-level keys: %s",
            list(document.keys()),
        )
        return []
