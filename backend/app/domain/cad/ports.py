"""The `cad` bounded context's port: what the domain needs from a CAD
engine, not how any particular engine does it.

Why this exists: we have four genuinely different candidate engines
(LibreDWG, ezdxf, ACadSharp, QCAD) with different strengths, and the honest
way to pick "the best combination" is to run the same read/write/round-trip
tests against all of them and compare real results - not to hardcode one
choice. See docs/CAD_ENGINE_FRAMEWORK.md for the benchmark this enables and
its current results, and docs/architecture/README.md for how this port fits
the domain/adapters/IoC pattern.

An engine declares what it can do via boolean flags (`reads_dwg`, etc.)
rather than every engine needing to implement every method - LibreDWG, for
example, is a format *converter* (DWG<->DXF), not an entity builder, so it
has no meaningful `write_dxf` capability of its own.
"""
from __future__ import annotations

from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path

from app.models.schemas import Geometry, TextItem


@dataclass
class ParsedDrawing:
    """Engine-agnostic drawing content - the common currency every engine
    reads into and writes from, so results are comparable apples-to-apples."""

    layers: list[str] = field(default_factory=list)
    geometries: list[Geometry] = field(default_factory=list)
    texts: list[TextItem] = field(default_factory=list)


class EngineError(RuntimeError):
    """Raised by a CadEnginePort adapter on a read/write/convert failure."""


class CadEnginePort(ABC):
    """Port: interface the domain defines for reading/writing CAD drawings.
    Adapters (app/adapters/cad/) implement it against a real engine; the
    domain and application layers depend only on this class, never on a
    concrete adapter - see app/bootstrap.py for the IoC wiring."""

    name: str
    open_source: bool
    reads_dwg: bool = False
    reads_dxf: bool = False
    writes_dwg: bool = False
    writes_dxf: bool = False

    def can_read(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        return (suffix == ".dwg" and self.reads_dwg) or (suffix == ".dxf" and self.reads_dxf)

    def can_write(self, path: Path) -> bool:
        suffix = path.suffix.lower()
        return (suffix == ".dwg" and self.writes_dwg) or (suffix == ".dxf" and self.writes_dxf)

    def read(self, path: Path) -> ParsedDrawing:
        raise NotImplementedError(f"{self.name} cannot read {path.suffix}")

    def write(self, drawing: ParsedDrawing, out_path: Path, version: str = "r2018") -> Path:
        raise NotImplementedError(f"{self.name} cannot write {out_path.suffix}")
