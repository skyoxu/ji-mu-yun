# Source Coverage

Machine owner: [`schemas/source-coverage.v1.json`](schemas/source-coverage.v1.json).

## Original Source Coverage

| Source identity | Requirement IDs |
| --- | --- |
| AGENT-SRC-I | RMAP-001, 002, 005, 011, 012, 020, 024 |
| AGENT-SRC-II | RMAP-003, 004, 006, 013, 017, 019, 021, 022 |
| AGENT-SRC-III | RMAP-005, 006, 010, 011, 012, 024 |
| AGENT-SRC-IV | RMAP-004, 006-010, 013-016, 021, 023, 025 |
| AGENT-SRC-V | RMAP-005, 010-012, 019, 024, 026 |
| AGENT-SRC-VI | RMAP-003-005, 007-011, 014, 015, 018 |
| AGENT-SRC-VII | RMAP-004-018, 020, 023 |
| AGENT-SRC-VIII | RMAP-001-006, 010, 013, 017, 021-024 |
| AGENT-SRC-IX | RMAP-001-019, 021-024 |

The machine owner declares ranges and exact arrays. The validator independently derives agentbuild section ranges from the hash-bound `---` separators and clarification selectors from the settled question set, then requires exact ID/selector equality. Section count and requirement-union equality alone are insufficient.

## Durable Clarification Coverage

| Decisions | Requirement IDs |
| --- | --- |
| CQ-001 to CQ-005 | RMAP-001-003, 005, 011, 012, 017, 019, 024 |
| CQ-006 to CQ-012 | RMAP-004, 005, 010, 013, 014, 017, 020, 022, 023 |
| CQ-013 to CQ-017 | RMAP-003, 014-017, 021 |
| Repair CQ-001 to CQ-005 | RMAP-003, 004, 006, 007, 010, 013, 014, 016-018, 021, 023 |
| Repair 20260717 CQ-001 to CQ-007 | RMAP-005, 010, 014, 015, 021, 024-026 |
| Repair 20260717 999 CQ-001 to CQ-007 | RMAP-001, 002, 010, 012, 014, 016, 020, 021, 023, 026 |
| Repair 20260717 1200 CQ-001 to CQ-005 | RMAP-002, 013, 014, 016, 020, 023 |
| Repair 20260717 1300 CQ-001 to CQ-005 | RMAP-012, 014, 026, 027 |
| Repair 20260718 1500 CQ-001 to CQ-005 | RMAP-004, 012, 015, 016, 018, 021, 027 |

The machine source is `schemas/clarification-decisions.v1.json`, not the ignored raw clarification run under `logs/**`.

## Exactness Rules

- Every active requirement appears in at least one original or clarification source mapping.
- Every mapped requirement exists exactly once in the requirement registry.
- Every requirement has one owner book, first phase, acceptance identity, evidence intent, and accountable implementation owner.
- Markdown summaries may group IDs; the JSON registry and coverage map own exact arrays.
- Future P4 requirements are not active in this plan.
