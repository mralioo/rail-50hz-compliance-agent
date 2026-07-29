"""CAD engine benchmark harness - the "test and change module to find the
best combination" tool. Runs every registered engine (app/cad_engines/) in
the same read / write / cross-read-back tests and prints a comparison
table, so switching or combining engines is a config choice backed by
numbers, not a guess. Findings get written up in
docs/CAD_ENGINE_FRAMEWORK.md; this script is how to reproduce or extend
them (add a fixture, add an engine, re-run).

Usage: python scripts/engine_bench.py  (from backend/)
"""
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from app.cad_engines import ENGINES, EngineError, ParsedDrawing
from app.models.schemas import Geometry, TextItem

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "samples"
OUT_DIR = Path(__file__).resolve().parents[1] / "data" / "samples" / "cad_engine_poc"
VERSIONS = ["r2000", "r2004", "r2007", "r2010", "r2013", "r2018"]

READ_FIXTURES = {
    "sample_plan.dxf": DATA_DIR / "sample_plan.dxf",
    "Kreuzungsplan.dwg": DATA_DIR / "DB" / "Kreuzungsplan.dwg",
}

DUMMY_DRAWING = ParsedDrawing(
    layers=["E_ROOM", "E_CABLE", "E_CABINET", "E_NOTES"],
    geometries=[
        Geometry(layer="E_ROOM", kind="polyline", points=[(0, 0), (6, 0), (6, 4), (0, 4)], closed=True),
        Geometry(layer="E_CABLE", kind="line", points=[(0.5, 3.5), (5.5, 0.5)]),
        Geometry(layer="E_CABLE", kind="circle", points=[(5.5, 0.5)], radius=0.1),
    ],
    texts=[TextItem(layer="E_NOTES", text="NYY-J 5x16 / R=150mm", position=(0.5, 2))],
)
EXPECTED_TEXT = "NYY-J 5x16 / R=150mm"


@dataclass
class Result:
    op: str
    engine: str
    detail: str
    ok: bool
    seconds: float
    note: str = ""


def timed(op: str, engine: str, detail: str, fn) -> Result:
    start = time.perf_counter()
    try:
        note = fn()
        return Result(op, engine, detail, True, time.perf_counter() - start, note or "")
    except EngineError as exc:
        return Result(op, engine, detail, False, time.perf_counter() - start, str(exc)[:200])
    except Exception as exc:  # noqa: BLE001 - benchmark must not crash on one bad combo
        return Result(op, engine, detail, False, time.perf_counter() - start, f"{type(exc).__name__}: {exc}"[:200])


def bench_reads(results: list[Result]) -> None:
    for fixture_name, path in READ_FIXTURES.items():
        if not path.exists():
            continue
        for name, engine in ENGINES.items():
            if not engine.can_read(path):
                continue

            def do_read(engine=engine, path=path):
                drawing = engine.read(path)
                return f"layers={len(drawing.layers)} geoms={len(drawing.geometries)} texts={len(drawing.texts)}"

            results.append(timed("read", name, fixture_name, do_read))


def bench_write_and_crossread(results: list[Result]) -> None:
    for suffix, capability in ((".dwg", "writes_dwg"), (".dxf", "writes_dxf")):
        writers = [(n, e) for n, e in ENGINES.items() if getattr(e, capability)]
        readers = [(n, e) for n, e in ENGINES.items() if e.can_read(Path("x" + suffix))]
        versions = VERSIONS if suffix == ".dwg" else ["r2018"]

        for version in versions:
            for writer_name, writer in writers:
                out_path = OUT_DIR / "bench" / f"{writer_name}_{version}{suffix}"

                def do_write(writer=writer, out_path=out_path, version=version):
                    writer.write(DUMMY_DRAWING, out_path, version)
                    return f"{out_path.stat().st_size}B"

                write_result = timed("write", writer_name, f"{version}{suffix}", do_write)
                results.append(write_result)
                if not write_result.ok:
                    continue

                for reader_name, reader in readers:
                    label = f"{writer_name}->{reader_name} {version}{suffix}"

                    def do_crossread(reader=reader, out_path=out_path):
                        drawing = reader.read(out_path)
                        texts = [t.text for t in drawing.texts]
                        ok_text = EXPECTED_TEXT in texts
                        return (
                            f"geoms={len(drawing.geometries)}/3 "
                            f"text_ok={ok_text}"
                        )

                    results.append(timed("cross-read", reader_name, label, do_crossread))


def print_table(results: list[Result]) -> None:
    width = max(len(f"{r.engine} {r.detail}") for r in results) + 2
    for r in results:
        status = "OK  " if r.ok else "FAIL"
        label = f"{r.engine} {r.detail}"
        print(f"[{r.op:10s}] {status} {label:<{width}} {r.seconds:6.3f}s  {r.note}")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[Result] = []
    bench_reads(results)
    bench_write_and_crossread(results)

    print_table(results)

    report_path = OUT_DIR / "bench_results.json"
    report_path.write_text(json.dumps([asdict(r) for r in results], indent=2))
    print(f"\n{sum(r.ok for r in results)}/{len(results)} operations succeeded.")
    print(f"Full report: {report_path}")


if __name__ == "__main__":
    main()
