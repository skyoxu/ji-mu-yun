# 8-06 Repair Reconciliation (2026-10-18)

This is a bounded requirements repair, not a new audit of every completion claim
in 8-05/8-24. Their completed/merged status is the maintainer's explicit input;
current main source was inspected to establish which owners must be preserved.
No historical status text or local-unavailable Windows run is promoted to proof.

## Baseline actually inspected

| Source at f7ac19d | Relevance to this repair |
| --- | --- |
| AGENTS.md and README.md | Three responsibility layers; protected paths; explicit directory repair route. |
| docs/workflows/skill-control-plane-evolution-requirements.md | Package A standard/validator/fixtures; Package B alone migrates five Skills. |
| .agents/skills/vdd-execution-plan/SKILL.md and its planning/solo-maintainer/lifecycle guides | Canonical compiler, governance-off controls, CER intent, current readiness ownership. |
| .agents/skills/quick-dev-tdd-adapter/SKILL.md and references/execution-operation.md | Current semantic input; Q2 test ownership; real case evidence; Q7/Q8 completion. |
| scripts/quick_dev/run.py and tools/q1_planned_preflight.py, tools/red_production_entry_guard.py under Quick Dev | Planned-input guards and real production binding; old v1 route is compatibility only. |
| .agents/skills/vdd-execution-plan/scripts/skill-contract.json | Existing owner-specific protocol; the quality sidecar must coexist with it. |
| PhaseA.Platform/Security/RunnerIsolationPolicy.cs | Existing OS identity/Job Object/ACL authority. Static Skill validation does not replace it. |
| PhaseA.Platform/Workspaces/RestoreService.cs | Existing account/lease/fence/recovery owner. No new runtime backup/restore system in Package A. |
| docs/adr/ADR-0058-toolchain-skill-replay-portability-and-evaluation-seeds.md | Preserved toolchain replay and evidence boundary. |
| docs/adr/ADR-0061-phase-b-c-identity-isolation-workspace-recovery-spine.md | Preserved Phase isolation/recovery boundary. |
| docs/architecture/ADR_INDEX_PHASE.md | ADR-0060 occupied by Skill-input; propose the next currently free ADR-0062 for Package A. |

Paths abbreviated as tools/... above are inside
`.agents/skills/quick-dev-tdd-adapter/`; these are read dependencies, not writes.
The old 8-05 root index still points to an unstarted RMAP-S0. It is historical
navigation, not evidence that the merged current implementation is absent.
This repair does not reopen 8-05, modify its evidence or retest Phase isolation.

## Original requirement coverage

| Original | Current intents / constraints | Disposition |
| --- | --- | --- |
| SAS-001 / SAS-A01 | A01, A10; NFR-1 | Retained; distinguish declared structure from semantic review. |
| SAS-002 / SAS-A02 | A02, A03, A06 | Retained; quality namespace does not overwrite owner-specific contracts. |
| SAS-003 / SAS-A03 | A07 | Retained: exactly three ordered primary examples; deterministic duplicate/branch checks plus external review of meaning. |
| SAS-004 / SAS-A04 | A08 | Retained only for actual routing/orchestration capability. |
| SAS-005 / SAS-A05 | A04, A05 | Retained original 499-pass/500-fail boundary; direct references and newline normalization explicit. |
| SAS-006 / SAS-A06 | A09, A10 | Retained; optional absence has declared safe fallback, required absence blocks. |
| SAS-007 / SAS-A07 | A06, A11, A20 | Retained as declaration/validator contracts; no executing arbitrary package commands. |
| SAS-008 / SAS-A08 | A12 | Retained; FAQ remains optional. |
| SAS-009 / SAS-A09 | A13, A14 | Retained; local-only N/A, external version records without mandatory live network/MCP. |
| SAS-010 / SAS-A10 | A15--A21; NFR-1 | Retained capability-conditioned checks; real enforcement remains with current owning systems. |
| SAS-011 / SAS-A11 | A22--A24 | Retained legacy/migrated fixtures and positive/boundary/negative cases; history preserved. |
| SAS-012 / SAS-A12 | A23--A25; NFR-2 | Retained terminal command and Package B handoff; no mandatory migration of real Skills in Package A. |

A01--A25 are authoring intents, not a claim that the compiler has emitted exactly
25 atomic obligations. Where a row has independent cases/oracles, VDD must
preserve each one during semantic decomposition.

## Concrete repairs

| Old problem | Current decision |
| --- | --- |
| Historical v1 implementation contract offered as the executable handoff | Compile current semantic artifacts inside current-plan/ and consume only that path. Root v1 remains read-only history. |
| Blocked Bootstrap Round 3 treated as a current prerequisite | No internal review activation; use current development governance rules and external review. |
| Historical frozen knowledge and Skill-input v1 receipts required globally | Inspect current scoped sources; no new governance attestations or knowledge-publication dependency. |
| ADR-0060 proposed for two incompatible purposes | New Package A ADR proposes 0062; collision recheck before implementation. |
| RED defined as absent files/nonzero exit; completion as present files | Replace with real pytest selectors, production calls, independent assertions and current CER/Q7/Q8. |
| S0 documents/config only, without an executable initial behavior lane | Foundation group includes the real validator entry plus schemas/policy; documentation constraints remain non-fabricated checks. |
| S2 required capability behavior but could not edit the owning validator | Each affected group declares the actual validator/policy owners; tests freeze separately. |
| Broad scripts/sc/** and docs/adr/** closures | Exact production allowlist and a bounded fixture subtree; no immutable snapshot of a mutable owner. |
| Early regression invoked future tests that did not yet exist | Q6 uses current and predecessor groups only; full four-module selection is terminal. |
| Terminal scanned all .agents/skills, effectively forcing Package B into A | Validate Package A policy/schemas and reference package only; real Skill migration stays separate. |
| 'Standard itself is a Skill package' interpretation | Standard policy/schemas plus a reference fixture demonstrate conformance; no installed total-entry/governance Skill. |
| Static safety statements sounded like runtime security proof | Explicitly separate declaration checks from 8-24 enforcement and 8-05 execution evidence. |
| Existing Skill owner schema could be replaced by a generic quality contract | A separate quality namespace/sidecar coexists with current owner-specific protocols. |
| Plan-local combined terminal writer could publish completion | Current Quick Dev Q7/Q8 and Acceptance retain their separate ownership. |

No new feature outside Package A was added. The explicit safety checks apply to
the validator's actual local file reads and to declared capability contracts;
they do not introduce a security scoring system, network gateway, tenant audit,
second storage backend, or new platform evidence framework.

## Historical preservation and current limitation

All 117 pre-existing files other than 00-index.md remain at their original paths
and unchanged; the original index bytes are copied beside this reconciliation.
Old failed review/repair evidence is never repurposed as current validation.
The new source and navigation supersede interpretation of old plan instructions,
not the historical events they record.

Canonical compilation was attempted through the public CLI. It reached the V1
worker and returned repair-vdd because codex is not in PATH. The temporary host
also has no configured OpenAI API credentials/SDK. The current source is not
labelled plan-ready. Deterministic source/navigation checks cannot substitute
for V1/V4 semantic work or current Quick Dev handoff validation. The exact local
continuation is in LOCAL-HANDOFF.md.
