"""Modular CAD engine framework - swap/compare read+write backends without
touching the production pipeline. See docs/CAD_ENGINE_FRAMEWORK.md.
"""
from app.cad_engines.base import CadEngine, EngineError, ParsedDrawing
from app.cad_engines.registry import ENGINES, get_engine

__all__ = ["CadEngine", "EngineError", "ParsedDrawing", "ENGINES", "get_engine"]
