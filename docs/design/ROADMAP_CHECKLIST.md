# GLEIS·OS — Roadmap Checklist

Companion to [`gleis-os-system-blueprint.html`](gleis-os-system-blueprint.html)
(§09 Roadmap). Five items, ordered by priority. Check off as work lands;
each item lists what it closes in the blueprint and the concrete first
steps grounded in the current codebase.

---

## 1. Formal Orchestrator — `Next`
*Replace the client-side regex router with a real coordinating agent that plans, sequences, and retries. Closes §03 → §04.*

- [ ] Inventory every intent the current regex router in `console_shell.html` /
      `chat_provider.dart` handles (locate, draw, plain chat) as an explicit
      task type
- [ ] Design an `Orchestrator` module (backend, not client-side JS) that
      accepts a raw instruction and returns a routing/plan decision
- [ ] Move routing logic server-side so both front doors (Flutter app,
      browser console) share one decision-maker instead of duplicating regex
- [ ] Add retry/error-handling semantics (today: none — a failed step just
      surfaces as an error to the engineer)
- [ ] Verify: same instruction routed identically from both front doors

## 2. A2A between existing agents — `Next`
*Give Compliance/Locator/Analyzer/Draftsman a peer-to-peer interface instead of being called as functions. Closes §04.*

- [ ] Pick a concrete A2A implementation/library (or a minimal in-house
      subset: task object, agent identity, capability declaration)
- [ ] Wrap one existing agent (`app/agent/locator.py` is the smallest,
      lowest-risk candidate) behind an A2A-style interface first
- [ ] Have the new Orchestrator (item 1) call that wrapped agent via A2A
      instead of a direct Python function call
- [ ] Repeat for Compliance, Analyzer, Draftsman once the pattern is proven
- [ ] Verify: an agent can be swapped/mocked without touching the caller,
      proving the interface is a real boundary and not just a rename

## 3. CAD Manipulation Agent — `Planned`
*The instruction → SOP retrieval → edit plan loop described in the blueprint's §06/§07, on top of the CAD engine framework that already exists. Closes §07.*

- [ ] Define the `DwgEditOp` contract for real (op, target layer/entity,
      citation, confidence) — sketched already in the blueprint's low-level
      section, not yet in `app/models/schemas.py`
- [ ] Build the retrieval step: instruction → matching SOP/Richtlinie clause
      via the existing `app/agent/rag.py` knowledge base
- [ ] Build the drafting step: retrieved clause + current DWG state (via
      `cad_engines/`) → a proposed `DwgEditOp[]`, not yet written
- [ ] Wire the proposal to require Verification Agent sign-off (item 4)
      before any write call reaches the CAD engine
- [ ] Verify end-to-end on one real, narrow instruction (e.g. "add earthing
      run, cabinet 2 → rail, per SOP-14") against a real DWG, human-approved

## 4. Verification Agent — `Planned`
*The clearance/norm re-check that has to exist before the CAD agent is trusted with a real write. Closes §02 · §07.*

- [ ] Define its input contract: a proposed `DwgEditOp` or a compliance
      finding, plus which knowledge base(s) to check against
- [ ] Re-run the same regulation-citation check the Compliance Agent uses,
      but scoped to the proposed edit's specific geometry/clause
- [ ] Add a geometric clearance check (distance/bending-radius math already
      exists in the pipeline — reuse rather than reimplement)
- [ ] Output: pass/flag + the exact violated clause, never a bare rejection
- [ ] Verify: a deliberately non-compliant proposed edit gets flagged with
      a correct, citeable reason

## 5. Broaden the knowledge base — `Planned`
*VDE corpus, more DB Richtlinien folders, and a real semantic index behind the Knowledge Steward. Closes §05.*

- [ ] Source and add a `vde/` folder under `backend/data/regulations/`
      (today only `general/` and `db/` are populated)
- [ ] Expand `db/` with more DB Netz-specific Richtlinien beyond
      `db_ril_954_9101.md`
- [ ] Replace keyword-matching retrieval in `app/agent/rag.py` with a real
      semantic/vector index (today: plain `glob` + keyword match)
- [ ] Re-seed Cognee memory (`python scripts/seed_memory.py`) after each
      corpus addition
- [ ] Verify: a question scoped to the new `vde` knowledge base returns a
      correctly cited excerpt from it, not a fallback to `general`

---

## Non-negotiables (apply to every item above)

- **Drafting, not deciding** — every agent output stays a proposal; final
  validation and legal liability stay with the certified engineer.
- **No claim without a citation** — a regulation-grounded answer that can't
  point to the exact retrieved clause doesn't ship as an answer.
- **No silent writes** — nothing touches the source DWG/DXF without an
  explicit, reviewable, human-approved step.
- **Every correction is logged** — an engineer's edit or rejection is
  training data, not a discarded event.
