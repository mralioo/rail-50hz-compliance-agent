import type { Finding } from "../api/types";

export interface CraftsmanSuggestion {
  op: "fillet_wire";
  radius: number;
  reason: string;
}

/** Maps a compliance finding to a suggested Craftsman fix, when one exists.
 * Deliberately narrow: only an actually-measured bending-radius violation
 * has an obvious 1:1 geometric op (round the corner to the required radius
 * via fillet_wire) - everything else (pulling force, citation drift, a
 * *warning* about a missing annotation with no measured value) has no
 * direct geometry fix, so returns null rather than guessing. Matches
 * `parameter` on substring, not an exact key, since its exact formatting
 * depends on which agent backend produced it (mock vs. LLM) - but requires
 * `non_compliant` (not `warning`) and a real mm figure in `actual` (the
 * measured value), not just `expected`, so a documentation-only warning
 * like "not specified in plan" can't match. */
export function suggestCraftsmanFix(finding: Finding): CraftsmanSuggestion | null {
  const param = finding.parameter.toLowerCase();
  if (finding.status !== "non_compliant" || !param.includes("bending")) return null;
  if (!/[\d.]+\s*mm/.test(finding.actual)) return null;

  const match = finding.expected.match(/([\d.]+)\s*mm/);
  const radius = match ? Number(match[1]) : 150;
  return {
    op: "fillet_wire",
    radius,
    reason: `${finding.parameter}: ${finding.actual} → ${finding.expected}`,
  };
}
