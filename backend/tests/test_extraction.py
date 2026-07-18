"""Pipeline extraction tests against a synthetic DXF (no ODA/GCP needed)."""
from pathlib import Path

import ezdxf
import pytest

from app.agent.client import MockAgentClient
from app.extraction.dxf_parser import parse_dxf
from app.extraction.geometry import compute_bounds, compute_metrics
from app.models.schemas import DataLayerPayload, FindingStatus


@pytest.fixture
def sample_dxf(tmp_path: Path) -> Path:
    doc = ezdxf.new("R2018")
    msp = doc.modelspace()
    doc.layers.add("E_ROOM")
    doc.layers.add("E_CABLE")
    doc.layers.add("E_NOTES")
    msp.add_lwpolyline([(0, 0), (10, 0), (10, 5), (0, 5)], close=True, dxfattribs={"layer": "E_ROOM"})
    msp.add_lwpolyline([(1, 1), (9, 1), (9, 4)], dxfattribs={"layer": "E_CABLE"})
    msp.add_text("R=90mm", dxfattribs={"layer": "E_NOTES"}).set_placement((2, 2))
    msp.add_text("acc. to Ril 954.0107", dxfattribs={"layer": "E_NOTES"}).set_placement((3, 3))
    path = tmp_path / "test.dxf"
    doc.saveas(path)
    return path


def test_parse_dxf_extracts_layers_and_entities(sample_dxf: Path) -> None:
    layers, geometries, texts = parse_dxf(sample_dxf)
    assert {"E_ROOM", "E_CABLE", "E_NOTES"} <= set(layers)
    assert len(geometries) == 2
    assert len(texts) == 2


def test_metrics_computed_from_geometry_and_annotations(sample_dxf: Path) -> None:
    _, geometries, texts = parse_dxf(sample_dxf)
    metrics = {m.name: m for m in compute_metrics(geometries, texts)}
    assert metrics["room_area"].value == pytest.approx(50.0)
    assert metrics["run_length"].value == pytest.approx(11.0)
    assert metrics["cable_bending_radius"].value == pytest.approx(90.0)
    assert compute_bounds(geometries) == (0.0, 0.0, 10.0, 5.0)


def test_mock_agent_flags_injected_violations(sample_dxf: Path) -> None:
    layers, geometries, texts = parse_dxf(sample_dxf)
    payload = DataLayerPayload(
        source_file="test.dxf",
        layers=layers,
        geometries=geometries,
        texts=texts,
        metrics=compute_metrics(geometries, texts),
        bounds=compute_bounds(geometries),
    )
    report = MockAgentClient().analyze(payload)
    non_compliant = [f for f in report.findings if f.status is FindingStatus.NON_COMPLIANT]
    parameters = {f.parameter for f in non_compliant}
    assert "Cable bending radius" in parameters  # 90 mm < 150 mm
    assert "Guideline citation (template drift)" in parameters  # Ril 954.0107
