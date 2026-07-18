"""Generate the demo plan: a switchgear room with two cable runs and
deliberately injected compliance violations for the agent to catch.

Injected errors:
- citation of retired guideline "Ril 954.0107"  -> template drift
- bending radius annotation "R=90mm"            -> below the 150 mm minimum
- pulling force annotation "pull: 620 N"        -> above the 500 N maximum

Usage: python scripts/make_sample_dxf.py  (from backend/)
"""
from pathlib import Path

import ezdxf

OUT = Path(__file__).resolve().parents[1] / "data" / "samples" / "sample_plan.dxf"


def main() -> None:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    for name, color in [("E_ROOM", 5), ("E_CABLE", 1), ("E_CABINET", 3), ("E_NOTES", 7)]:
        doc.layers.add(name, color=color)

    # Switchgear room outline: 12 m x 8 m
    msp.add_lwpolyline(
        [(0, 0), (12, 0), (12, 8), (0, 8)], close=True, dxfattribs={"layer": "E_ROOM"}
    )
    # Control cabinet footprint
    msp.add_lwpolyline(
        [(1, 6), (3.2, 6), (3.2, 7.5), (1, 7.5)], close=True, dxfattribs={"layer": "E_CABINET"}
    )
    # Cable run A (compliant)
    msp.add_lwpolyline([(3.2, 6.5), (8, 6.5), (8, 2), (11, 2)], dxfattribs={"layer": "E_CABLE"})
    # Cable run B (tight bend, annotated below)
    msp.add_lwpolyline([(3.2, 7), (10, 7), (10, 0.5)], dxfattribs={"layer": "E_CABLE"})
    # Cable entry point
    msp.add_circle((11, 2), radius=0.15, dxfattribs={"layer": "E_CABLE"})

    notes = {"layer": "E_NOTES", "height": 0.25}
    msp.add_text("NYY-J 5x16 / R=90mm", dxfattribs=notes).set_placement((9.6, 7.3))
    msp.add_text("max pull: 620 N", dxfattribs=notes).set_placement((5, 6.8))
    msp.add_text("acc. to Ril 954.0107", dxfattribs=notes).set_placement((0.5, 0.3))
    msp.add_text("Schaltraum UV 50Hz", dxfattribs=notes).set_placement((5, 4))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
