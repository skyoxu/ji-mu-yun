# Requirements Ledger

Machine owner: [`schemas/requirements.v1.json`](schemas/requirements.v1.json).

Executable acceptance owner: [`schemas/acceptance-contracts.v1.json`](schemas/acceptance-contracts.v1.json). Requirement quality is derived against current requirement and acceptance hashes rather than accepted from self-declared booleans.

| ID | Requirement | Owner | First phase | Acceptance | Status |
| --- | --- | --- | --- | --- | --- |
| RMAP-001 | Reuse ADR-0041 for the shared ownership pattern and Bootstrap boundary, not TDD Adapter semantics, and reject ADR-ID collisions. | workflow architect | P0 | RMAP-ACC-001 | active |
| RMAP-002 | Enforce durable standard / repository Skill / compatibility adapter / plan / logs ownership boundaries. | workflow architect | P0 | RMAP-ACC-002 | active |
| RMAP-003 | Provide one compact implementation-contract instance per participating plan. | contract maintainer | P0 | RMAP-ACC-003 | active |
| RMAP-004 | Enforce structured commands, shell=false, env allowlist, and typed placeholders. | command-contract maintainer | P0 | RMAP-ACC-004 | active |
| RMAP-005 | Keep adapter v1 stateless, in-session, and free of provider scheduling. | adapter maintainer | P1 | RMAP-ACC-005 | active |
| RMAP-006 | Fail prepare on invalid plan, contract, predecessor, hash, path, command, or blocker state. | adapter maintainer | P1 | RMAP-ACC-006 | active |
| RMAP-007 | Require an actually observed expected RED before production writes. | TDD gate maintainer | P1 | RMAP-ACC-007 | active |
| RMAP-008 | Permit minimal GREEN only from current RED evidence and declared write sets. | TDD gate maintainer | P1 | RMAP-ACC-008 | active |
| RMAP-009 | Permit REFACTOR only after GREEN while preserving declared regression checks. | TDD gate maintainer | P1 | RMAP-ACC-009 | active |
| RMAP-010 | Emit an exact cumulative Git/attempt-fold candidate envelope that authorizes Bootstrap review only. | evidence maintainer | P1 | RMAP-ACC-010 | active |
| RMAP-011 | Keep implementation backends neutral and without review/done/commit authority. | backend-contract maintainer | P1 | RMAP-ACC-011 | active |
| RMAP-012 | Preserve Bootstrap as the single semantic-review authority and consume its repository-owned finalized-run envelope. | review integration maintainer | P3 | RMAP-ACC-012 | active |
| RMAP-013 | Expose exact plan-ready, slice-ready, implementation-candidate, and implementation-accepted predicates. | plan validator maintainer | P0 | RMAP-ACC-013 | active |
| RMAP-014 | Freeze Git/index/closure identity plus byte-verifiable baseline file snapshots. | baseline maintainer | P1 | RMAP-ACC-014 | active |
| RMAP-015 | Recover from append-only evidence with stale predecessor and normally initialized successor runs. | recovery maintainer | P1 | RMAP-ACC-015 | active |
| RMAP-016 | Consume an explicit non-superseded S6 candidate reference plus a current finalized-run envelope and block on open P0/P1 or invalid P2 disposition. | acceptance maintainer | P3 | RMAP-ACC-016 | active |
| RMAP-017 | Backfill 7-12, 7-07, and 7-11 additively and validate them only in shadow mode. | migration maintainer | P2 | RMAP-ACC-017 | active |
| RMAP-018 | Test contract, lifecycle, recovery, shadow, supportive, neutral, and competing scenarios. | test maintainer | P1 | RMAP-ACC-018 | active |
| RMAP-019 | Limit this plan to P0-P3 and move BMAD removal to a future plan. | plan owner | P0 | RMAP-ACC-019 | active |
| RMAP-020 | Keep confidence advisory and cap internal improvement at three rounds. | plan validator maintainer | P0 | RMAP-ACC-020 | active |
| RMAP-021 | Keep plan-owned immutable intent separate from logs-owned mutable run evidence. | evidence maintainer | P0 | RMAP-ACC-021 | active |
| RMAP-022 | Preserve and hash-bind agentbuild.txt without duplicating source authority. | source custodian | P0 | RMAP-ACC-022 | active |
| RMAP-023 | Enforce Windows containment, case normalization, protected paths, and reparse-point safety. | path-security maintainer | P1 | RMAP-ACC-023 | active |
| RMAP-024 | Prevent a new Router or expansion of historical script directories without an ADR delta. | workflow architect | P0 | RMAP-ACC-024 | active |
| RMAP-025 | Persist immutable Capsules with typed refs and an exact byte-verified artifact union. | context protocol maintainer | P0 | RMAP-ACC-025 | active |
| RMAP-026 | Preserve complete ordered stage attempts, exact event lifecycle, cumulative accepted-attempt folding, and ledger-root candidate binding. | attempt protocol maintainer | P0 | RMAP-ACC-026 | active |

Each acceptance identity is executable intent. The machine registry owns source refs, evidence intent, consumers, failure family, and quality-check status.
