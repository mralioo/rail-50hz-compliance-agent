import type { CraftsmanOp } from "../api/types";

export interface SopStep {
  n: number;
  title: string;
  description: string;
  /** Builds the real CraftsmanOp for this step against whatever object id
   * is "current" when the step runs — chained onto the previous step's
   * actual output (see JobCraftsman's runSop: each Craftsman call re-reads
   * the original upload, so a multi-step SOP is a real sequence of calls,
   * each targeting the object the previous one just created). */
  buildOp: (targetId: string) => CraftsmanOp;
}

export interface Sop {
  id: string;
  name: string;
  requirement: string;
  steps: SopStep[];
}

/**
 * Real, executable SOPs against the 3 real Craftsman ops (see
 * docs/CRAFTSMAN_AGENT.md) - not the Anvil mockup's fictional machining
 * steps. Each step is a genuine `POST /jobs/{id}/craftsman` call; running
 * the SOP chains them by tracking the newly-created object id after each
 * step (JobCraftsman.runSop), the same way an engineer would work through
 * it by hand one op at a time.
 */
export const SOPS: Sop[] = [
  {
    id: "cable-bend-radius",
    name: "Cable Bend-Radius Remediation",
    requirement:
      "Bring a non-compliant cable route into compliance with DB Ril 954.0107 (minimum 150mm bend radius) and restore wall clearance.",
    steps: [
      {
        n: 1,
        title: "Join fragmented route segments",
        description:
          "The imported route may have landed as several disconnected line/arc segments — join them into one continuous wire before editing it.",
        buildOp: (id) => ({ op: "upgrade_objects", ids: [id] }),
      },
      {
        n: 2,
        title: "Offset the route for wall clearance",
        description: "Move the joined route 150mm clear of its current position.",
        buildOp: (id) => ({ op: "offset_wire", id, delta: [150, 0, 0] }),
      },
      {
        n: 3,
        title: "Round the corner to the minimum bend radius",
        description: "Fillet the route's first corner to the DB Ril 954.0107 minimum of 150mm.",
        buildOp: (id) => ({ op: "fillet_wire", id, radius: 150, edge_indices: [0, 1] }),
      },
    ],
  },
  {
    id: "route-realignment",
    name: "Full Route Realignment",
    requirement:
      "A longer remediation pass: join, realign twice around an obstruction, then fillet both new corners to spec.",
    steps: [
      {
        n: 1,
        title: "Join fragmented route segments",
        description: "Join disconnected segments into one wire.",
        buildOp: (id) => ({ op: "upgrade_objects", ids: [id] }),
      },
      {
        n: 2,
        title: "Offset around the obstruction (pass 1)",
        description: "First 100mm offset to clear the obstruction's near edge.",
        buildOp: (id) => ({ op: "offset_wire", id, delta: [100, 0, 0] }),
      },
      {
        n: 3,
        title: "Offset around the obstruction (pass 2)",
        description: "Second 80mm offset to clear the obstruction's far edge.",
        buildOp: (id) => ({ op: "offset_wire", id, delta: [0, 80, 0] }),
      },
      {
        n: 4,
        title: "Round the first new corner",
        description: "Fillet the corner introduced by pass 1 to the 150mm minimum.",
        buildOp: (id) => ({ op: "fillet_wire", id, radius: 150, edge_indices: [0, 1] }),
      },
      {
        n: 5,
        title: "Offset the tail clear of the wall",
        description:
          "Draft.make_fillet keeps only the 2 edges it's given, so the filleted wire from " +
          "step 4 is now just those 2 trimmed edges plus the new arc — the rest of the " +
          "original wire is gone and there's no second corner left to fillet. Finish with " +
          "a clearance offset on what remains instead.",
        buildOp: (id) => ({ op: "offset_wire", id, delta: [50, 0, 0] }),
      },
    ],
  },
];
