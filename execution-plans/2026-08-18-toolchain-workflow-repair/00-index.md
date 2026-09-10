# Toolchain Workflow Repair

This plan owns the workflow-level repairs identified during the
acceptance-coordinator trust review. It is separate from the
`acceptance-coordinator-trust-recovery` implementation plan and does not alter
the 2026-08-17 historical plans.


## Current direct repair

The 2026-09-10 source audit reopened the earlier direct closeout. Four gaps
have now been corrected: required-input mapping, authority-bound candidate
changes, live v2 entry enforcement, and automatic native-use retention.
Implementation, test scope and migration instructions are recorded in
[Direct closeout](direct-closeout.md) and [Skill-input v2](../../docs/workflows/skill-input-v2.md).

Online verification: 164 passed, one Windows-only case deselected. Fresh
Windows verification of this revision is pending (165 cases expected).
Earlier 139-case success and closeout records remain historical; they do not
validate the new source. No formal workflow or live backend was invoked.

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


