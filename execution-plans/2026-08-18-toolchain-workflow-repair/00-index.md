# Toolchain Workflow Repair

This plan owns the workflow-level repairs identified during the
acceptance-coordinator trust review. It is separate from the
`acceptance-coordinator-trust-recovery` implementation plan and does not alter
the 2026-08-17 historical plans.


## Current direct repair

The maintainer authorized direct online implementation of the complete W0-W6
scope without the formal execution chain. Current implementation and local
verification instructions are in [Direct closeout](direct-closeout.md).
The new shared entry is `scripts/python/skill_input_v2.py`; run
`py -3 scripts/python/verify_toolchain_workflow_repair.py` for direct validation.
The full W0-W6 direct repair is closed based on the maintainer-reported Windows
validation of 86faa3e0: 139 passed, zero skipped, stable sources, and no platform
exclusions. See Direct closeout for the evidence location and provenance.
This closes the authorized direct repair on this branch; it is not a merge or
a formal workflow acceptance. The older lifecycle statement below and formal
receipts are historical, not current direct-closeout evidence.

## Scope

- W0: typed source selection and authority/read-set projection.
- W1: adapter-owned transport planning, pagination, and continuation.
- W2: adapter-owned coverage and truncation decisions.
- W3: Knowledge execution, publication, and review gates.
- W4: immutable receipt generation and canonical current pointer.
- W5: leased attempts, retention protection, and approval-gated garbage
  collection.
- W6: end-to-end migration verification across W0-W5.

## Explicit Non-goals

- No automatic Knowledge publication.
- No Bootstrap startup or lifecycle publication.
- No changes to Phase runtime or user-sandbox state.

## Historical formal lifecycle (superseded procedure)

The historical formal plan state is `implementation-authorized`, following VDD-owned
plan-ready validation and an explicit maintainer receipt. Implementation may
begin only through the declared Quick Dev TDD route; this plan does not
authorize implementation completion, Knowledge publication, Bootstrap, or
acceptance.

