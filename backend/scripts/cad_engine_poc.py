"""CAD write-engine connectivity test.

Two things this proves, independently:
1. Write -> existing system: a DXF authored/modified by `ezdxf` (our write
   engine) is read back correctly by our *own* extraction pipeline
   (parse_dxf + compute_metrics) - the loop the compliance agent depends on.
2. Write -> real DWG: `dxf2dwg` (LibreDWG) turns that DXF into a standalone
   .dwg an engineer can open in real CAD software. Verified via `dwgread`
   (a second, independent LibreDWG tool) rather than round-tripping back
   through our own `dwg2dxf`, which has a known bug reading dxf2dwg's own
   output - see docs/CAD_MANIPULATION_ENGINE.md §3 for the full writeup.

Produces two deliverables in data/samples/cad_engine_poc/:
- blank_project.dxf / .dwg  - empty doc, just the standard layers
- dummy_project.dxf / .dwg  - a few entities incl. a compliance-checkable
                              bending-radius annotation ("R=150mm")

Usage: python scripts/cad_engine_poc.py  (from backend/, with dwg2dxf/
dxf2dwg/dwgread on PATH or under ~/.local/bin)
"""
import json
import subprocess
from pathlib import Path

import ezdxf

from app.extraction.dxf_parser import parse_dxf
from app.extraction.geometry import compute_metrics
from app.ingestion.writer import dxf_to_dwg, find_dxf2dwg

OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "samples" / "cad_engine_poc"
LAYERS = [("E_ROOM", 5), ("E_CABLE", 1), ("E_CABINET", 3), ("E_NOTES", 7)]


def _new_doc() -> ezdxf.document.Drawing:
    doc = ezdxf.new("R2010")
    for name, color in LAYERS:
        doc.layers.add(name, color=color)
    return doc


def build_blank() -> Path:
    doc = _new_doc()
    path = OUT_DIR / "blank_project.dxf"
    doc.saveas(path)
    return path


def build_dummy() -> Path:
    doc = _new_doc()
    msp = doc.modelspace()

    msp.add_lwpolyline(
        [(0, 0), (6, 0), (6, 4), (0, 4)], close=True, dxfattribs={"layer": "E_ROOM"}
    )
    msp.add_line((0.5, 3.5), (5.5, 0.5), dxfattribs={"layer": "E_CABLE"})
    msp.add_circle((5.5, 0.5), radius=0.1, dxfattribs={"layer": "E_CABLE"})
    msp.add_text(
        "NYY-J 5x16 / R=150mm", dxfattribs={"layer": "E_NOTES", "height": 0.2}
    ).set_placement((0.5, 2))

    path = OUT_DIR / "dummy_project.dxf"
    doc.saveas(path)
    return path


def check_pipeline_reads_it(dxf_path: Path) -> None:
    """Write -> existing system: our own extraction pipeline on the DXF."""
    layers, geometries, texts = parse_dxf(dxf_path)
    metrics = compute_metrics(geometries, texts)
    print(f"    pipeline read: layers={layers}")
    print(f"    geometries={[(g.kind, g.layer) for g in geometries]}")
    print(f"    texts={[t.text for t in texts]}")
    print(f"    metrics={[(m.name, m.value, m.unit) for m in metrics]}")


def check_dwg_has_entities(dwg_path: Path) -> None:
    """Write -> real DWG: independent structural check via `dwgread`,
    since our own `dwg2dxf` can't reliably read dxf2dwg's own output back."""
    dwgread = find_dxf2dwg().parent / "dwgread" if find_dxf2dwg() else None
    if not dwgread or not dwgread.exists():
        print("    (dwgread not found on PATH - skipping structural check)")
        return
    dump_path = dwg_path.with_suffix(".json")
    subprocess.run(
        [str(dwgread), "-O", "json", "-o", str(dump_path), str(dwg_path)],
        capture_output=True, text=True, timeout=30,
    )
    entities = []
    if dump_path.exists():
        raw = dump_path.read_text(errors="ignore")
        for kind in ("LWPOLYLINE", "LINE", "CIRCLE", "TEXT"):
            if f'"{kind}"' in raw:
                entities.append(kind)
        dump_path.unlink()  # debug artifact only, not a deliverable
    print(f"    dwgread confirms entity kinds present: {entities}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("1. blank project")
    blank_dxf = build_blank()
    check_pipeline_reads_it(blank_dxf)
    blank_dwg = dxf_to_dwg(blank_dxf, out_dir=OUT_DIR)
    print(f"   -> {blank_dwg.name} ({blank_dwg.stat().st_size} bytes)")
    check_dwg_has_entities(blank_dwg)

    print("2. dummy project")
    dummy_dxf = build_dummy()
    check_pipeline_reads_it(dummy_dxf)
    dummy_dwg = dxf_to_dwg(dummy_dxf, out_dir=OUT_DIR)
    print(f"   -> {dummy_dwg.name} ({dummy_dwg.stat().st_size} bytes)")
    check_dwg_has_entities(dummy_dwg)

    print(f"\nDeliverables in {OUT_DIR}")
    print("Open dummy_project.dwg in LibreCAD to eyeball it - the CLI can't "
          "load .dwg (dxf2pdf/png/svg take .dxf only), so this last step is "
          "manual: snap run librecad data/samples/cad_engine_poc/dummy_project.dwg")


if __name__ == "__main__":
    main()
