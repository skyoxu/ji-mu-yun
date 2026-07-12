# Source Coverage

## Required Books

- 00 index
- 01 authority/threat model/Gates
- 02 Permit trust/attestation
- 03 Profiles/Preflight/containment
- 04 Mutation/lease/journal/acceptance
- 05 React `/ui-v2`
- 06 platform architecture/Data/version
- 07 evidence/telemetry/performance
- 08 implementation phases
- 09 risks/DoD/glossary
- 96 global review/validation
- 97 post-split ledger
- 98 split audit
- 99 source coverage

## Required Machine Artifacts

- `schemas/bootstrap-handoff-contract.v1.schema.json`
- `schemas/upstream-handoff-manifest.v1.schema.json`
- `schemas/upstream-handoff-state-event.v1.schema.json`
- `schemas/upstream-handoff-active-registry.v1.schema.json`
- `schemas/upstream-completion-snapshot.v1.schema.json`
- `schemas/handoff-source-map.v1.schema.json`
- `schemas/downstream-observation-snapshots.v1.schema.json`
- `schemas/finding-closure-registry.v1.schema.json`
- `schemas/finding-closure-evidence.v1.schema.json`
- `schemas/original-requirement-family-registry.v1.schema.json`
- `schemas/original-requirement-family-registry.v1.json`
- generated `schemas/finding-closure-registry.v1.json`
- explicit `schemas/finding-closure-evidence.v1.json`
- `schemas/schema-validation-fixtures.v1.json`
- `tools/validate_whole_directory.py`

## Coverage Dimensions

| Dimension | Covered by |
| --- | --- |
| Business authority separation | top-level, 00, 01 |
| Strict sequential upstream handoff and immutable source binding | top-level, 01, 08, 96, 97 |
| Threat/trust/attestation | 01, 02 |
| Signer/test evidence/workspace-manifest trust | 02 |
| Codex actor profiles, broker IPC, Platform enforcement and Acceptance containment | 03 |
| File/non-file mutation recovery, complete states and capacity reservation | 04 |
| Browser auth/session/concurrency/policy/React migration/supply chain/trial thresholds | 05 |
| Internal architecture/maintainability/Data/online DB migration/release compatibility | 06 |
| Protected evidence custody/quotas/operations/SLO/performance fixtures | 07 |
| Sequencing/task closure | 08 |
| Risks/terminology/DoD | 09 |
| Mechanical plan validation | 96 |
| New requirement preservation | 97 |
| Historical source mapping | 98 |
| Machine-readable handoff and review contracts | schemas/** |
| Historical finding closure and freshness | 97, generated finding closure registry, 96 validator |
| AGENTS/README truthfulness and phase-bound synchronization | 08, AGENTS.md, README.md |
| Original 19-family semantic coverage | original-family registry, 98, 99 |

## Assertions

- Every `PBR-*` entry is owned and represented in this coverage map.
- No required book is missing or unlinked.
- Top-level recovery metadata remains valid: UpstreamHandoffActiveRegistry selects one immutable Manifest and recovery reads that Manifest's `finalCommit`; no static Git Head or registry-owned commit is authoritative.
- Upstream GDD-to-module business semantics are referenced, not copied.
- Durable implemented rules are moved out of execution plans into standards/ADR/workflow.

## Explicit PBR Coverage

| Owner/phase coverage | PBR IDs |
| --- | --- |
| top-level / BH-HANDOFF activation and recovery | PBR-016, PBR-056 |
| 01 / BH-HANDOFF sequential closure, external handoff root and completion snapshot | PBR-040, PBR-041, PBR-060, PBR-065 |
| 01 / BH-HANDOFF frozen bootstrap contract, external lock/signer, state registry, source map, derived observations and final-ready history | PBR-071, PBR-072, PBR-073, PBR-074, PBR-075, PBR-076, PBR-078, PBR-084 |
| 01 / BH-SF0A host-admin-resistant trust | PBR-050 |
| 01 / BH-SF0B handoff epoch/deferral runtime invalidation | PBR-066 |
| 01 / BH-SF0B supersession disposition and no-rebind | PBR-081 |
| 02 / BH-SF0A trust ceremony | PBR-004 |
| 02 / BH-SF0B Permit, signer, attestation, manifests, DR/restore epoch, key history and SLO | PBR-001, PBR-005, PBR-017, PBR-018, PBR-019, PBR-023, PBR-035, PBR-039, PBR-052, PBR-053, PBR-054, PBR-068 |
| 03 / BH-SF1 Platform/Hosted containment, independent clone/apply fence, broker and host-admin-resistant runner | PBR-006, PBR-007, PBR-020, PBR-022, PBR-025, PBR-049, PBR-059, PBR-067 |
| 03 / BH-SF2 Change Origin Gate and Preflight integration | PBR-026 |
| 04 / BH-SF3 Mutation, fenced/OS-locked apply, internal Acceptance projection, recovery block, quarantine and reserve | PBR-002, PBR-011, PBR-012, PBR-021, PBR-024, PBR-031, PBR-051, PBR-062, PBR-069 |
| 04 / BH-PILOT imported Work Policy | PBR-044 |
| 07 / BH-SF0B minimum trusted evidence | PBR-037 |
| 07 / BH-HANDOFF bootstrap evidence custody | PBR-077 |
| 07 / BH-SF4 evidence boundary, operations and performance | PBR-014, PBR-015, PBR-034, PBR-038, PBR-045 |
| 05 / BH-REACT1 auth/security/supply-chain/surface projection/trial | PBR-008, PBR-009, PBR-010, PBR-027, PBR-028, PBR-029, PBR-036, PBR-043, PBR-057 |
| 05 / BH-REACT2 compatibility-preserving migration | PBR-048 |
| 06 / BH-ARCH architecture ratchet | PBR-032, PBR-055 |
| 06 / BH-SF0A standards delta-chain foundation | PBR-063 |
| 06 / BH-DATA schema handoff and online migration | PBR-030, PBR-046 |
| 06 / BH-RELEASE rollback and standards ownership | PBR-003, PBR-047 |
| 08 / BH-HANDOFF phase decomposition and strict predecessor graph | PBR-058, PBR-064 |
| 08 / BH-SF1 containment feasibility go/no-go | PBR-082 |
| 96 / BH-HANDOFF overlap validator, handoff-only task and frozen self-modification guard | PBR-033, PBR-042, PBR-061, PBR-070; PBR-013 is historical and resolves through the status registry |
| 97 / BH-HANDOFF machine-readable PBR supersession | PBR-083 |
| top-level / BH-HANDOFF exact formal Gates and ActiveRegistry recovery baseline | PBR-079, PBR-080 |
| 96 / BH-HANDOFF local plan-readiness versus protected verifier boundary and top-level authority owner | PBR-085, PBR-091 |
| 01 / BH-HANDOFF actual schemas, qualified source paths and constrained deferrals | PBR-086, PBR-095, PBR-097 |
| 01 / BH-SF0B complete handoff binding tuple | PBR-092 |
| 97 / BH-HANDOFF generated finding closure, bidirectional mapping, stable acceptance and derived terminology | PBR-087, PBR-088, PBR-089, PBR-094 |
| 98 / BH-HANDOFF canonical original semantic-family coverage | PBR-090 |
| 08 / BH-HANDOFF phase-bound AGENTS/README synchronization | PBR-098 |
| 05 / BH-REACT1 predecessor gate and derived surface vocabulary | PBR-093, PBR-099 |
| 09 / BH-SF1 consistent containment stop condition | PBR-096 |
| 06 / BH-DATA checkpointed retry return | PBR-100 |
| 09 / BH-SF0A machine-object glossary completeness | PBR-101 |
| 01 / BH-HANDOFF strict commit/hash, signature, dual-snapshot, qualified source-map path and schema identity contracts | PBR-102, PBR-103, PBR-104, PBR-105, PBR-112 |
| 96 / BH-HANDOFF Draft 2020-12 schema and fixture validation | PBR-106 |
| 99 / BH-HANDOFF structural owner/phase coverage and ActiveRegistry-to-Manifest recovery relation | PBR-107, PBR-111 |
| 97 / BH-HANDOFF explicit finding closure evidence independent of PBR mapping | PBR-108 |
| 01 / BH-HANDOFF strict downstream observation, deferral and source-map N-A contracts | PBR-109, PBR-110, PBR-115 |
| 98 / BH-HANDOFF approved original semantic provenance and machine-readable acceptance | PBR-113, PBR-116 |
| 06 / BH-DATA retryTargetState vocabulary without a persisted placeholder state | PBR-114 |

The split validator parses this table and requires every ledger ID exactly once, except an explicitly superseded historical ID which must resolve through the Requirement Status Registry to one active replacement. Owner and phase must match the ledger row.

## Original Requirement Family Coverage

| Family | Owner books | Acceptance ref |
| --- | --- | --- |
| ORIG-01 | top-level, 00, 01 | phase-boundary://original-requirements/ORIG-01/acceptance |
| ORIG-02 | 01 | phase-boundary://original-requirements/ORIG-02/acceptance |
| ORIG-03 | 01, 08 | phase-boundary://original-requirements/ORIG-03/acceptance |
| ORIG-04 | 02 | phase-boundary://original-requirements/ORIG-04/acceptance |
| ORIG-05 | 02 | phase-boundary://original-requirements/ORIG-05/acceptance |
| ORIG-06 | 03 | phase-boundary://original-requirements/ORIG-06/acceptance |
| ORIG-07 | 03 | phase-boundary://original-requirements/ORIG-07/acceptance |
| ORIG-08 | 04 | phase-boundary://original-requirements/ORIG-08/acceptance |
| ORIG-09 | 04 | phase-boundary://original-requirements/ORIG-09/acceptance |
| ORIG-10 | 05 | phase-boundary://original-requirements/ORIG-10/acceptance |
| ORIG-11 | 05 | phase-boundary://original-requirements/ORIG-11/acceptance |
| ORIG-12 | 05 | phase-boundary://original-requirements/ORIG-12/acceptance |
| ORIG-13 | 06 | phase-boundary://original-requirements/ORIG-13/acceptance |
| ORIG-14 | 06 | phase-boundary://original-requirements/ORIG-14/acceptance |
| ORIG-15 | 06 | phase-boundary://original-requirements/ORIG-15/acceptance |
| ORIG-16 | 07 | phase-boundary://original-requirements/ORIG-16/acceptance |
| ORIG-17 | 07 | phase-boundary://original-requirements/ORIG-17/acceptance |
| ORIG-18 | 08, 96 | phase-boundary://original-requirements/ORIG-18/acceptance |
| ORIG-19 | 09 | phase-boundary://original-requirements/ORIG-19/acceptance |

This table mirrors the canonical registry. It is semantic-family coverage, not a claim that the unavailable pre-split bytes or prose order were preserved.

## Completion

Coverage is complete only when the deterministic plan-readiness validator passes, the generated finding closure registry has no open plan finding, all 116 PBR requirements and all 19 approved original semantic families are mapped, and no global review finding identifies an unmapped requirement. This result means the plan is implementable; it does not mean implementation is complete and does not satisfy protected BH-HANDOFF validation.
