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
Windows validation remains pending. The older lifecycle statement below and
formal receipts are historical, not current direct-closeout evidence.

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

The plan is currently `implementation-authorized`, following VDD-owned
plan-ready validation and an explicit maintainer receipt. Implementation may
begin only through the declared Quick Dev TDD route; this plan does not
authorize implementation completion, Knowledge publication, Bootstrap, or
acceptance.

