"""Compliance agent implementations.

`MockAgentClient` is deterministic and credential-free — it keeps the demo
alive without GCP. `VertexAgentClient` sends the same payload to a Vertex AI
model grounded with retrieved regulation text. Select via AGENT_MODE.
"""
import json
import re
from abc import ABC, abstractmethod
from collections import Counter

from app.agent import rag
from app.core.config import get_settings
from app.models.schemas import (
    ComplianceReport,
    DataLayerPayload,
    Finding,
    FindingStatus,
)


CHAT_SYSTEM_PROMPT = (
    "You are a compliance assistant for DACH railway electrical planning "
    "engineers, discussing one specific 50 Hz auxiliary power plan. Answer "
    "the engineer's question conversationally in concise plain text — NEVER "
    "output JSON or code blocks, and use no markdown syntax at all (no **, "
    "no #, no tables; plain dashed lists are fine). Ground every statement in "
    "the provided compliance report, plan data and regulation excerpts; cite "
    "the regulation (e.g. Ril 954.9101 §4.2) when relevant. If something is "
    "not in the data, say so. Liability for final validation remains with "
    "the human engineer."
)


def _strip_markdown(text: str) -> str:
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # **bold**
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"`([^`\n]+)`", r"\1", text)  # inline code
    return re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)  # headings


def ensure_prose(reply: str) -> str:
    """Guard for the chat UI: models ignore formatting instructions at times,
    so JSON is flattened to text and markdown markers are stripped here."""
    text = reply.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    if not (text.startswith("{") and text.endswith("}")):
        return _strip_markdown(text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    lines: list[str] = []
    for finding in data.get("findings", []):
        lines.append(
            f"[{finding.get('status', '?')}] {finding.get('parameter', '?')}: "
            f"{finding.get('actual', '?')} (expected {finding.get('expected', '?')})"
            + (f" — {finding['suggestion']}" if finding.get("suggestion") else "")
        )
    if summary := data.get("summary"):
        lines.append(str(summary))
    return _strip_markdown("\n".join(lines)) or text


def payload_digest(payload: DataLayerPayload) -> str:
    """Compact prompt form of a payload.

    Real-world plans produce payloads of hundreds of KB (a 907 KB DXF gave a
    243 KB / ~62k-token JSON); sending them verbatim would blow the prompt
    budget. Length metrics are aggregated per layer, while every annotation is
    kept — text carries the compliance-relevant signal (citations, R=/N values).
    """
    kinds = Counter(g.kind for g in payload.geometries)
    special: list[str] = []
    agg: dict[tuple[str, str | None, str], tuple[float, int]] = {}
    for m in payload.metrics:
        if m.name in ("cable_bending_radius", "cable_pulling_force"):
            special.append(f"{m.name}={m.value:g}{m.unit} (layer {m.layer})")
        else:
            total, count = agg.get((m.name, m.layer, m.unit), (0.0, 0))
            agg[(m.name, m.layer, m.unit)] = (total + m.value, count + 1)

    annotations = " | ".join(
        f"{t.text} @({t.position[0]:.0f},{t.position[1]:.0f}) [{t.layer}]"
        for t in payload.texts if t.text
    )
    return "\n".join([
        f"file: {payload.source_file}",
        f"bounds (min_x,min_y,max_x,max_y): {payload.bounds}",
        "layers: " + ", ".join(payload.layers),
        "entity counts: " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())),
        "metrics per layer: " + ("; ".join(
            f"{name}[{layer}]: count={count}, total={total:.1f}{unit}"
            for (name, layer, unit), (total, count) in sorted(agg.items())
        ) or "none"),
        "electrical parameters: " + ("; ".join(special) or "none found in annotations"),
        "annotations: " + (annotations or "none"),
    ])


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


class OpenAIAgentClient(AgentClient):
    """OpenAI-backed analyst. Requires AGENT_MODE=openai + OPENAI_API_KEY."""

    def __init__(self) -> None:
        from openai import OpenAI  # deferred: optional dependency

        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError("AGENT_MODE=openai requires OPENAI_API_KEY in backend/.env")
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model
        self._instruction = (settings.prompts_dir / "instruction.md").read_text(encoding="utf-8")

    def analyze(self, payload: DataLayerPayload) -> ComplianceReport:
        regulations = "\n\n".join(rag.retrieve("cable bending radius pulling force deprecated"))
        response = self._client.chat.completions.create(
            model=self._model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self._instruction},
                {
                    "role": "user",
                    "content": (
                        f"## Regulatory Context\n{regulations}\n\n"
                        f"## Structured CAD Data (digest)\n{payload_digest(payload)}"
                    ),
                },
            ],
        )
        return ComplianceReport.model_validate(json.loads(response.choices[0].message.content))

    def chat(self, message, payload, report) -> str:
        context = [f"Regulations:\n" + "\n".join(rag.retrieve(message))]
        if report:
            context.append(f"Compliance report:\n{report.model_dump_json()}")
        if payload:
            context.append(
                f"Plan layers: {', '.join(payload.layers)}; "
                f"metrics: {'; '.join(f'{m.name}={m.value:g}{m.unit}' for m in payload.metrics[:30])}"
            )
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": CHAT_SYSTEM_PROMPT},
                {"role": "user", "content": "\n\n".join(context) + f"\n\nEngineer: {message}"},
            ],
        )
        return ensure_prose(response.choices[0].message.content or "")


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
            f"## Structured CAD Data (digest)\n{payload_digest(payload)}"
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
            contents=f"{CHAT_SYSTEM_PROMPT}\n\n{chr(10).join(context_parts)}\n\nEngineer: {message}",
        )
        return ensure_prose(response.text or "")


def get_agent() -> AgentClient:
    mode = get_settings().agent_mode
    if mode == "openai":
        return OpenAIAgentClient()
    if mode == "vertex":
        return VertexAgentClient()
    return MockAgentClient()
