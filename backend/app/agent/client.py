"""Compliance agent implementations.

`MockAgentClient` is deterministic and credential-free — it keeps the demo
alive without GCP. `VertexAgentClient` sends the same payload to a Vertex AI
model grounded with retrieved regulation text. Select via AGENT_MODE.
"""
import json
from abc import ABC, abstractmethod

from app.agent import rag
from app.core.config import get_settings
from app.models.schemas import (
    ComplianceReport,
    DataLayerPayload,
    Finding,
    FindingStatus,
)


class AgentClient(ABC):
    @abstractmethod
    def analyze(self, payload: DataLayerPayload) -> ComplianceReport: ...

    @abstractmethod
    def chat(
        self,
        message: str,
        payload: DataLayerPayload | None,
        report: ComplianceReport | None,
    ) -> str: ...


class MockAgentClient(AgentClient):
    """Rule-based validator against the machine-readable DB Ril limits."""

    def analyze(self, payload: DataLayerPayload) -> ComplianceReport:
        rules = rag.load_rules()
        findings: list[Finding] = []

        for metric in payload.metrics:
            if metric.name == "cable_bending_radius":
                ok = metric.value >= rules.min_bending_radius_mm
                findings.append(
                    Finding(
                        status=FindingStatus.COMPLIANT if ok else FindingStatus.NON_COMPLIANT,
                        parameter="Cable bending radius",
                        actual=f"{metric.value:g} mm",
                        expected=f">= {rules.min_bending_radius_mm:g} mm",
                        regulation="Ril 954.9101 §4.2",
                        location=metric.layer,
                        suggestion=None if ok else "Re-route the cable run with a wider bend.",
                    )
                )
            elif metric.name == "cable_pulling_force":
                ok = metric.value <= rules.max_pulling_force_n
                findings.append(
                    Finding(
                        status=FindingStatus.COMPLIANT if ok else FindingStatus.NON_COMPLIANT,
                        parameter="Cable pulling force",
                        actual=f"{metric.value:g} N",
                        expected=f"<= {rules.max_pulling_force_n:g} N",
                        regulation="Ril 954.9101 §4.2",
                        location=metric.layer,
                        suggestion=None if ok else "Split the pull or use a cable lubricant plan.",
                    )
                )

        for text in payload.texts:
            for code in rag.load_rules().deprecated_codes:
                if code in text.text:
                    findings.append(
                        Finding(
                            status=FindingStatus.NON_COMPLIANT,
                            parameter="Guideline citation (template drift)",
                            actual=code,
                            expected=" / ".join(rules.active_codes),
                            regulation="Ril 954.9101 §4.5",
                            location=f"{text.layer} @ ({text.position[0]:g}, {text.position[1]:g})",
                            suggestion=f"Replace citation of retired {code} with the active guideline.",
                        )
                    )

        bad = sum(1 for f in findings if f.status is FindingStatus.NON_COMPLIANT)
        summary = (
            f"Checked {len(payload.metrics)} extracted parameters across "
            f"{len(payload.layers)} layers: {bad} non-compliant finding(s). "
            "Final validation remains with the responsible engineer."
        )
        return ComplianceReport(findings=findings, summary=summary)

    def chat(self, message, payload, report) -> str:
        if report is None:
            return "Upload and process a plan first — then I can answer compliance questions."
        context = rag.retrieve(message)
        lines = [f"- [{f.status.value}] {f.parameter}: {f.actual} (expected {f.expected})"
                 for f in report.findings]
        reply = "Current compliance state:\n" + ("\n".join(lines) or "- no findings")
        if context:
            reply += "\n\nRelevant regulation excerpt:\n" + context[0][:400]
        return reply


class VertexAgentClient(AgentClient):
    """Vertex AI (Gemini) adapter. Requires AGENT_MODE=vertex + GCP_PROJECT."""

    def __init__(self) -> None:
        from google import genai  # deferred: optional dependency

        settings = get_settings()
        self._client = genai.Client(
            vertexai=True, project=settings.gcp_project, location=settings.vertex_location
        )
        self._model = settings.vertex_model
        self._instruction = (settings.prompts_dir / "instruction.md").read_text(encoding="utf-8")

    def analyze(self, payload: DataLayerPayload) -> ComplianceReport:
        regulations = "\n\n".join(rag.retrieve("cable bending radius pulling force deprecated"))
        prompt = (
            f"{self._instruction}\n\n## Regulatory Context\n{regulations}\n\n"
            f"## Structured CAD Data\n```json\n{payload.model_dump_json(indent=2)}\n```"
        )
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        return ComplianceReport.model_validate(json.loads(response.text))

    def chat(self, message, payload, report) -> str:
        context_parts = [f"Regulations:\n{chr(10).join(rag.retrieve(message))}"]
        if report:
            context_parts.append(f"Compliance report:\n{report.model_dump_json()}")
        response = self._client.models.generate_content(
            model=self._model,
            contents=f"{self._instruction}\n\n{chr(10).join(context_parts)}\n\nEngineer: {message}",
        )
        return response.text


def get_agent() -> AgentClient:
    if get_settings().agent_mode == "vertex":
        return VertexAgentClient()
    return MockAgentClient()
