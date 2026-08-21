"""Crop individual pictures out of Docling's full-page renders.

Ported from the ITUKI backend (DoclingConversionAdapter). Docling does not
embed per-picture bytes even with ``image_export_mode=embedded``; instead the
converted-document JSON gives us:

  - ``document.pages[page_no].image.uri``  full-page render (base64 PNG)
  - ``document.pages[page_no].size``        page size in document units
  - ``document.pictures[i].prov[0].bbox``  picture box (BOTTOMLEFT origin)

This module decodes each page render once, converts each BOTTOMLEFT bbox to
PIL (top-left) pixel coordinates, and crops the picture out. Pictures are
returned in Docling document order (``position_index``) so callers can name
files and write references deterministically - important for the AEC
schematics/electrical plans in this corpus, where picture order carries
meaning (sheet layout, legend, detail views).
"""
import base64
import hashlib
import io
import logging
from dataclasses import dataclass, field
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)

# Skip crops smaller than this (decorative fragments or crop artifacts)
_MIN_IMAGE_BYTES = 512


@dataclass
class ExtractedImage:
    data: bytes
    mime_type: str
    checksum: str
    position_index: int
    page_number: int | None = None
    bounding_box: dict | None = None
    caption: str | None = None
    classification: str | None = None
    description: str | None = None
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def find_pictures(document: dict) -> list[dict]:
    for field_name in ("pictures", "figures", "images"):
        value = document.get(field_name)
        if isinstance(value, list) and value:
            return value
    return []


def extract_images(document: dict) -> list[ExtractedImage]:
    """Crop every picture from the page renders in ``document``.

    Returns them in document order. Silent-skips (logged at debug) any picture
    with missing provenance, an undecodable page render, or a degenerate box -
    one bad picture must never abort a whole document.
    """
    if not document:
        return []
    pictures = find_pictures(document)
    if not pictures:
        return []

    pages_dict = document.get("pages") or {}
    page_renders: dict[int, Image.Image] = {}
    images: list[ExtractedImage] = []

    for idx, pic in enumerate(pictures):
        prov_list = pic.get("prov") or []
        if not prov_list:
            continue
        prov = prov_list[0]
        page_no = prov.get("page_no") or prov.get("page_number")
        bbox = prov.get("bbox")
        if page_no is None or not isinstance(bbox, dict):
            continue

        if page_no not in page_renders:
            page_img = _decode_page_render(pages_dict, page_no)
            if page_img is None:
                continue
            page_renders[page_no] = page_img
        page_img = page_renders[page_no]

        crop_box = _bbox_to_pil_crop(
            bbox, page_img.size, _page_size(pages_dict, page_no)
        )
        if crop_box is None:
            continue
        try:
            cropped = page_img.crop(crop_box)
        except Exception:
            logger.debug("crop failed for picture [%d]", idx, exc_info=True)
            continue

        img_bytes = _to_png_bytes(cropped)
        if len(img_bytes) < _MIN_IMAGE_BYTES:
            continue

        images.append(
            ExtractedImage(
                data=img_bytes,
                mime_type="image/png",
                checksum=hashlib.sha256(img_bytes).hexdigest(),
                position_index=idx,
                page_number=int(page_no),
                bounding_box=bbox,
                caption=_first_caption(pic),
                classification=_classification(pic),
                width=cropped.width,
                height=cropped.height,
                size_bytes=len(img_bytes),
            )
        )

    logger.info("extracted %d / %d picture(s)", len(images), len(pictures))
    return images


def _first_caption(pic: dict) -> str | None:
    captions = pic.get("captions") or []
    if captions and isinstance(captions, list):
        first = captions[0]
        return first.get("text") if isinstance(first, dict) else str(first)
    return None


def _classification(pic: dict) -> str | None:
    """Best predicted picture class, when picture-classification was on."""
    ann = pic.get("annotations") or []
    for a in ann:
        if not isinstance(a, dict):
            continue
        classes = a.get("predicted_classes") or a.get("predicted_class")
        if isinstance(classes, list) and classes:
            top = classes[0]
            if isinstance(top, dict):
                return top.get("class_name") or top.get("label")
        if isinstance(classes, str):
            return classes
    return None


def _decode_page_render(pages_dict: dict, page_no: int) -> "Image.Image | None":
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
        encoded = uri.split(",", 1)[1] if uri.startswith("data:") else uri
        return Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGBA")
    except Exception:
        logger.debug("failed to decode page %s render", page_no, exc_info=True)
        return None


def _page_size(pages_dict: dict, page_no: int) -> tuple[float, float] | None:
    page = pages_dict.get(str(page_no)) or pages_dict.get(page_no)
    if not isinstance(page, dict):
        return None
    size = page.get("size")
    if isinstance(size, dict):
        w, h = size.get("width"), size.get("height")
        if w and h:
            return float(w), float(h)
    return None


def _bbox_to_pil_crop(
    bbox: dict,
    img_size: tuple[int, int],
    page_size: tuple[float, float] | None,
) -> tuple[int, int, int, int] | None:
    """Convert a Docling BOTTOMLEFT bbox (l/b/r/t) to a PIL crop box.

    PIL is top-left origin, so y is flipped against the page height.
    """
    x_left, y_bottom = bbox.get("l"), bbox.get("b")
    x_right, y_top = bbox.get("r"), bbox.get("t")
    if None in (x_left, y_bottom, x_right, y_top):
        return None

    bl, bb, br, bt = float(x_left), float(y_bottom), float(x_right), float(y_top)
    img_w, img_h = img_size

    if page_size:
        page_w, page_h = page_size
        scale_x, scale_y = img_w / page_w, img_h / page_h
    else:
        scale_x = scale_y = 1.0
        page_h = float(img_h)

    left = max(0, min(int(bl * scale_x), img_w))
    top = max(0, min(int((page_h - bt) * scale_y), img_h))
    right = max(0, min(int(br * scale_x), img_w))
    bottom = max(0, min(int((page_h - bb) * scale_y), img_h))

    if right <= left or bottom <= top:
        return None
    return (left, top, right, bottom)


def _to_png_bytes(img: "Image.Image") -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()
