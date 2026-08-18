# Toolchain Workflow Repair

This draft plan owns the workflow-level repairs identified during the
acceptance-coordinator trust review. It is separate from the
`acceptance-coordinator-trust-recovery` implementation plan and does not alter
the 2026-08-17 historical plans.

## Scope

- W0: typed source selection and authority/read-set projection.
- W1: adapter-owned transport planning, pagination, and continuation.
- W2: adapter-owned coverage and truncation decisions.
- W3: Knowledge execution, publication, and review gates.

## Explicit Non-goals

- No automatic Knowledge publication.
- No Bootstrap startup or lifecycle publication.
- No W4 current-pointer redesign.
- No W5 lease, retry, or garbage-collection redesign.
- No changes to Phase runtime or user-sandbox state.

The plan remains `draft` until a VDD contract, write-set, and maintainer
authorization are produced.
