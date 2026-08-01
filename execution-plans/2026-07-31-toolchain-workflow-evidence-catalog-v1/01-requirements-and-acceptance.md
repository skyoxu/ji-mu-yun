# Requirements And Acceptance

This file is the compact owner for v1 intent, requirement coverage, and observable acceptance. `docs/know8.txt` is the user-approved design input; this plan narrows it into independently executable slices without implementing later roadmap directories.

| ID | Slice | Requirement | Observable acceptance |
| --- | --- | --- | --- |
| TEC-001 | TEC-S0 | Add one narrow Accepted ADR deciding only native ownership, derived/non-authorizing catalog status, lifecycle non-interference, and Phase hosted exclusion. | ADR text and index checks reject future Miner, Curator, review topology, context loading, or ranking policy as part of this decision. |
| TEC-002 | TEC-S0 | Preserve producer-native evidence and lifecycle authority. | Static and fixture checks prove catalog output always has `authorizes: []` and cannot publish `plan-ready`, `implementation-complete`, `acceptance-passed`, or `archived`. |
| TEC-003 | TEC-S0 | Hard-exclude Phase hosted/runtime/account evidence from v1. | Requests naming `logs/phase-a-innernet/**`, Hosted workspaces, account activity, or browser/API evidence fail before traversal. |
| TEC-004 | TEC-S1 | Define versioned Entity, Artifact, Relation, Projection, and Generation Envelope schemas without treating every native object as a run. | Schema vectors accept the declared record families and reject a universal workflow-run identity requirement. |
| TEC-005 | TEC-S1 | Derive stable Entity and Artifact Binding identities from repository, canonical producer, producer-native identity, normalized path role, and content binding where applicable. | Rebuild, duplicate-content, Windows case normalization, and collision vectors pass with stable non-colliding IDs. |
| TEC-006 | TEC-S1 | Use one closed producer ID set consistently in registry and all record types. | Unknown, inconsistent, or adapter-substituted producer IDs fail validation. |
| TEC-007 | TEC-S1 | Require an explicit producer registry and explicit request roots with adapter-validated root kinds. | Unregistered producer/root pairs and wildcard discovery fail; registry paths alone do not authorize traversal. |
| TEC-008 | TEC-S1 | Enforce resolved containment, repository-relative output, Windows case normalization, case-collision rejection, and symlink/junction/reparse escape and cycle rejection. | Detached hostile-path fixtures fail closed without reading outside their declared roots. |
| TEC-009 | TEC-S1 | Classify sources as `native_state_authority`, `execution_fact`, `supplemental_evidence`, `narrative_report`, or `derived_view`. | Only allowlisted native state/execution facts may establish status or Relation; narrative and derived inputs cannot. |
| TEC-010 | TEC-S2 | Add pull-only adapters for VDD, Quick Dev, Bootstrap Review, and Refactor Implementation Acceptance. | Each adapter consumes only explicit roots and producer-native manifests/contracts; producer trees remain byte-identical after scan. |
| TEC-011 | TEC-S2 | Preserve native status as dimension, value, and hash-bound reference, including unknown/unmapped states. | Adapter fixtures retain producer vocabulary and never force binary success/failure. |
| TEC-012 | TEC-S2 | Emit a Relation only from explicit hash-bound native evidence. | Proximity, time, filename, commit, common directory, and narrative-reference negative vectors emit no edge. |
| TEC-013 | TEC-S2 | Distinguish route selection, launch, and import facts. | A route file alone can emit `selects_route` only; `launches` and `imports` require their own native identities and evidence. |
| TEC-014 | TEC-S2 | Prevent nested Artifact Views, attempt workspaces, acceptance snapshots, copied Skill snapshots, test fixtures, and historical control-plane copies from becoming duplicate producer entities. | Nested-copy fixture produces only the outer formal artifact/entity set. |
| TEC-015 | TEC-S3 | Build an immutable generation from a registry, adapter hashes, explicit scan request, source manifests, and projection policy. | `build-generation` writes staging only and repeated identical semantic inputs yield the same `semantic_generation_hash`. |
| TEC-016 | TEC-S3 | Validate generation structure and native source freshness read-only. | `validate-generation` reports stale/fail on missing or drifted source bytes and never writes Current/LKG or producer evidence. |
| TEC-017 | TEC-S3 | Treat a legitimate new producer state as a new generation input, not corruption. | A changed but valid native fixture builds a new generation while the prior generation validates stale against current sources. |
| TEC-018 | TEC-S3 | Provide bounded read-only inspection commands. | `inspect-entity`, `inspect-artifact`, `list-relations`, `trace-native-evidence`, and `compare-generations` return safe metadata and hash references without raw sensitive bodies. |
| TEC-019 | TEC-S4 | Separate build, validate, publish, and restore authority. | Only explicit `publish-generation` may atomically advance Current/LKG; build and validate cannot. |
| TEC-020 | TEC-S4 | Preserve Current/LKG on failed build, validation, or activation and record append-only sidecar evidence. | Fault-injection vectors verify prior pointers byte-for-byte and retain non-authorizing failure evidence. |
| TEC-021 | TEC-S4 | Revalidate all native source references before `restore-lkg`. | Missing, drifted, escaped, or invalid native evidence blocks restore; successful restore advances only verified derived pointers. |
| TEC-022 | TEC-S5 | Prove one detached synthetic VDD -> Quick Dev -> Acceptance -> Bootstrap -> repair -> import -> terminal/disposition closure using real v1 schemas and validators without an LLM or live logs. | Every Entity and edge traces to a hash-bound producer-native fixture; no relation relies on inferred order or directory layout. |
| TEC-023 | TEC-S5 | Prove hard exclusions and source-byte immutability across all adapters and commands. | Before/after manifests match for producer roots, and Phase/nested/escape fixtures fail before content registration. |
| TEC-024 | TEC-S5 | Prove delete-and-rebuild consistency. | Removing only the detached derived generation and rebuilding yields the same semantic generation hash and stable IDs. |
| TEC-025 | TEC-S6 | Expose one terminal full validation command covering schemas, registry, adapters, identity/path safety, build/query, publication/recovery, detached closure, no-authority, and forbidden producer mutations. | The registered terminal command exits zero and is the only predicate that may support `implementation-complete`; acceptance remains external. |

Every requirement maps one-to-one to acceptance ID `TEC-ACC-<number>`, preserving the same three-digit suffix.

## CLI Contract

Required commands are `scan-producer`, `build-generation`, `validate-generation`, `publish-generation`, `inspect-entity`, `inspect-artifact`, `list-relations`, `trace-native-evidence`, `compare-generations`, and `restore-lkg`. All take an explicit repository root and bounded input paths. `build-generation` never publishes; `validate-generation` is read-only; `publish-generation` is the only Current/LKG writer; `restore-lkg` revalidates native evidence.

The CLI must not expose unbounded `scan-repository`, `discover-all-runs`, `infer-relations`, or `normalize-status` operations.

## Native Evidence Boundary

Adapters use producer-specific allowlists. Content hash proves bytes, not semantic identity. Catalog `authorizes: []` describes the derived record only and does not erase native artifact semantics. Unknown relations remain absent. Unknown status remains `unknown` or `unmapped` with its native dimension and reference preserved.

Global exclusions include `logs/phase-a-innernet/**`, Artifact View content roots, attempt workspaces, acceptance snapshots, nested Skill snapshots, simulated formal-run fixtures, and copied historical control planes. Generic names such as `snapshot` or `frozen-artifacts` are not excluded without producer-contract evidence because they may be formal outer artifacts.

## Non-Goals

This directory does not implement workflow evaluation metrics, label provenance, combined review, review-input navigation, progressive context loading, Experience Memory, Miner or Self-Questioning, Skill Candidate or Curator state, promotion, eligibility cohorts, canary traffic, rollback execution, learned ranking, offline RL, Phase hosted evidence, account isolation, audit export, or browser/API integration. It does not change any existing producer route, schema, lifecycle owner, or controlling validator.

## Acceptance Boundary

Targeted slice commands authorize no lifecycle state. `TEC-S6` may support only `implementation-complete` after the current terminal full validator passes. Refactor Implementation Acceptance remains responsible for `acceptance-passed`. Bootstrap implementation conformance may be requested as supplemental evidence, but it is not a plan-ready requirement and cannot publish lifecycle state.
