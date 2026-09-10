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

The W3 stale-context successor path is also corrected: frozen evidence is
preserved while catalog membership and current source bytes are verified for
a derived successor.

The W3 revision passed Windows verification: 179 passed, zero skipped; evidence
is archived in `logs/toolchain-workflow-repair-direct/20260910T122218Z-acdb64a8/`.
A subsequent audit found and repaired the Acceptance coordinator's legacy
receipt loader. Its v2 pointer and target binding now have eight direct regressions.
Current online verification: 186 passed, one Windows-only case deselected.
Windows verification of the coordinator repair passed: **187 passed**, zero
skipped, `source_stable=true`, no platform exclusions, and no pending Windows
verification. Raw evidence is archived in
`logs/toolchain-workflow-repair-direct/20260910T134123Z-71905052/`.
W0-W6 are closed within the maintainer-approved direct implementation and
validation scope; see Direct closeout for the validation boundaries.
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



