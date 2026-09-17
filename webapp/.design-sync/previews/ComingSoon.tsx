import { ComingSoon } from "../../src/components/shared/ComingSoon";

export function WithDocLink() {
  return (
    <ComingSoon
      entry={{
        slug: "semantic-kb",
        title: "Semantic & Graph Knowledge Store",
        eyebrow: "Knowledge base",
        description:
          "OpenSearch (vector/semantic retrieval) and Neo4j (explicit citation/supersession relationships) as a replacement for the regulation corpus's current keyword-match retrieval.",
        statusNote:
          "Evaluation PoC only — a working Docker Compose stack and ingestion scripts exist, but neither store is wired into any live endpoint (feature-flagged off by default).",
        docLink: {
          href: "https://github.com/mralioo/rail-50hz-compliance-agent/blob/main/docs/OPENSEARCH_NEO4J_EVALUATION.md",
          label: "Read the evaluation doc",
        },
      }}
    />
  );
}

export function WithoutDocLink() {
  return (
    <ComingSoon
      entry={{
        slug: "verification-agent",
        title: "Verification Agent",
        eyebrow: "Agent roster",
        description:
          "A pre-write guardrail that re-checks any proposed edit or finding against the knowledge base and geometric clearances before it's applied.",
        statusNote: "Not started",
      }}
    />
  );
}
