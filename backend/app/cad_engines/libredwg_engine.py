"""LibreDWG adapter - a format *converter* (dwg2dxf / dxf2dwg), not an
entity builder. It has no API to construct a LINE/CIRCLE/TEXT from scratch;
`write()` here is a composition of `EzdxfEngine` (builds the DXF) followed by
`dxf2dwg` (converts it to DWG) - documented as such rather than pretended
to be a native DWG writer. See docs/CAD_MANIPULATION_ENGINE.md §3 for the
hands-on findings this reflects (dxf2dwg drops entities at r2004; r2000 DWGs
it writes can't be read back by its own dwg2dxf, only by a second reader).
"""
import tempfile
from pathlib import Path

from app.cad_engines.base import CadEngine, EngineError, ParsedDrawing
from app.cad_engines.ezdxf_engine import EzdxfEngine
from app.extraction.dxf_parser import parse_dxf
from app.ingestion.converter import ConversionError, convert_dwg
from app.ingestion.writer import WriteError, dxf_to_dwg


class LibreDwgEngine(CadEngine):
    name = "libredwg"
    open_source = True
    reads_dwg = True
    writes_dwg = True

    def read(self, path: Path) -> ParsedDrawing:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dxf_path = convert_dwg(path, out_dir=Path(tmp))
                layers, geometries, texts = parse_dxf(dxf_path)
        except ConversionError as exc:
            raise EngineError(f"libredwg: {exc}") from exc
        return ParsedDrawing(layers=layers, geometries=geometries, texts=texts)

    def write(self, drawing: ParsedDrawing, out_path: Path, version: str = "r2000") -> Path:
        try:
            with tempfile.TemporaryDirectory() as tmp:
                dxf_path = EzdxfEngine().write(drawing, Path(tmp) / "staged.dxf", version)
                dwg_path = dxf_to_dwg(dxf_path, out_dir=out_path.parent, version=version)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            dwg_path.rename(out_path)
        except WriteError as exc:
            raise EngineError(f"libredwg: {exc}") from exc
        return out_path
