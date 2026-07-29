"""Registry of available CAD engines, keyed by name.

The point of the registry (rather than importing each engine directly) is
to let `scripts/engine_bench.py` and any future config-driven engine
selection iterate "every engine we have" without hardcoding the list in
more than one place.
"""
from app.cad_engines.acadsharp_engine import AcadSharpEngine
from app.cad_engines.base import CadEngine
from app.cad_engines.ezdxf_engine import EzdxfEngine
from app.cad_engines.libredwg_engine import LibreDwgEngine
from app.cad_engines.qcad_engine import QCadEngine

ENGINES: dict[str, CadEngine] = {
    "ezdxf": EzdxfEngine(),
    "libredwg": LibreDwgEngine(),
    "acadsharp": AcadSharpEngine(),
    "qcad": QCadEngine(),
}


def get_engine(name: str) -> CadEngine:
    try:
        return ENGINES[name]
    except KeyError:
        raise KeyError(f"Unknown CAD engine '{name}', available: {list(ENGINES)}") from None
