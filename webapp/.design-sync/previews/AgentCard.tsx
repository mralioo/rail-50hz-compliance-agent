import { AgentCard } from "../../src/components/agents/AgentCard";

export function Persona() {
  return (
    <AgentCard
      agent={{
        name: "Compliance Analyst",
        role: "Structured findings against Ril / VDE regulations",
        capabilities: [
          "Runs on every processed job — bending radius, pulling force, and other Ril 954.9101 / VDE 0100-520 limits",
          "3 selectable backends: mock (deterministic, offline), OpenAI, Vertex (Gemini)",
          "Produces the compliant / non-compliant / warning findings shown in the console's Findings tab",
        ],
        persona: true,
      }}
    />
  );
}

export function NonPersona() {
  return (
    <AgentCard
      agent={{
        name: "Knowledge Steward",
        role: "Regulation corpus + retrieval (non-persona)",
        capabilities: [
          "Parses machine-readable limit blocks out of the regulation markdown corpus (general / db / vde)",
          "Backs both the Compliance Analyst's deterministic checks and Plan Copilot's chat grounding",
        ],
        persona: false,
      }}
    />
  );
}
