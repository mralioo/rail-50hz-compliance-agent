"""IoC composition root.

The one place that knows about concrete adapters and wires them to the
domain ports they implement. Application/API code asks bootstrap for a
port implementation by name/config; it never imports an adapter class
directly. Grows one bounded context at a time as the migration in
docs/architecture/MIGRATION_MAP.md proceeds - today it wires `cad` only.
"""
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
