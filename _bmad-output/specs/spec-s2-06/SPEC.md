---
id: SPEC-s2-06
package_schema: canonical-spec-package.v1
companions:
  - path: _bmad-output/specs/spec-s2-06/identity-and-persistence.md
    role: normative_companion
  - path: _bmad-output/specs/spec-s2-06/consumer-and-role-boundaries.md
    role: normative_companion
  - path: _bmad-output/specs/spec-s2-06/shared-content-and-notifications.md
    role: normative_companion
  - path: _bmad-output/specs/spec-s2-06/verification-and-traceability.md
    role: normative_companion
  - path: _bmad-output/planning-artifacts/architecture/architecture-s2-06-20261028/ARCHITECTURE-SPINE.md
    role: adopted_companion
sources:
  - path: docs/requirements/s2-06/source/step2/S2-06/S2-06-requirements.md
    role: provenance
  - path: docs/requirements/s2-06/source/00-shared-scope-and-contracts.md
    role: provenance
  - path: docs/requirements/s2-06/source/01-dependencies-and-delivery.md
    role: provenance
  - path: _bmad-output/planning-artifacts/prds/prd-s2-06-20261028/prd.md
    role: provenance
  - path: _bmad-output/planning-artifacts/prds/prd-s2-06-20261028/addendum.md
    role: provenance
---

> **Canonical contract.** This SPEC, its four normative companions and its adopted Architecture Spine form the complete S2-06 planning contract. Sources are absorbed provenance. This is design authoring, not implementation or runtime acceptance.

> **Architecture handoff.** Read the adopted [Architecture Spine](../../planning-artifacts/architecture/architecture-s2-06-20261028/ARCHITECTURE-SPINE.md) alongside this contract; its local AD-14..AD-26 remain proposed pending owner ADR-0061 adoption before protected implementation, while inherited parent AD-1..AD-13 retain their Accepted authority.

# S2-06 Stable Node Identity and Test Role Boundaries

## Why

Accounts and projects need stable physical ownership before later packages add capacity and separated nodes. Current single-node identity and Runner foundations are reusable, but addresses and service processes must never define home. S2-06 makes server-owned home and entry/production responsibilities explicit while keeping existing test projects usable.

## Capabilities

- **CAP-1** — Stable physical identity (S2-06-FR01)
  - **intent:** Operators can keep physical node identity while access addresses and process diagnostics change.
  - **success:** Endpoint/port or instance change preserves node, account and project identities; login/workbench/active-content purposes are explicit.

- **CAP-2** — Server-owned account home (S2-06-FR02)
  - **intent:** The service keeps every account project, package, snapshot and execution on its one authoritative home.
  - **success:** Forged, missing or mismatched home cannot authorize access, execution or silent relocation.

- **CAP-3** — Persistent test binding (S2-06-FR03)
  - **intent:** Existing test accounts retain a server-bound single test node across additive upgrade and restart.
  - **success:** Binding and existing projects survive restart; readback declares single_node_test and never automatic placement.

- **CAP-4** — Actual-node enforcement (S2-06-FR04)
  - **intent:** Every local project read, write and execution respects physical ownership in addition to account authorization.
  - **success:** Home/project/actual-node mismatch is denied before file access or execution, without remote fallback.

- **CAP-5** — Logical role separation (S2-06-FR05)
  - **intent:** Entry and production duties are distinguishable when co-located for tests.
  - **success:** Entry-only keeps allowed login/home-routing/admin duties while ordinary workbench/projects/Runner production is unavailable.

- **CAP-6** — Role-aware dispatch (S2-06-FR06)
  - **intent:** Disabled production responsibility stops ordinary production through HTTP, services and background consumers.
  - **success:** Creation, all queue families, recovery and publication cannot bypass disabled role; cancellation and verified cleanup retain existing bounds.

- **CAP-7** — Honest capacity interface (S2-06-FR07)
  - **intent:** Consumers can distinguish node online state, account acceptance policy and measured readiness.
  - **success:** Unmeasured capacity is invalid with no fabricated reference; physical node is the counting key.

- **CAP-8** — Protected ownership configuration (S2-06-FR08)
  - **intent:** Project content and process diagnostics cannot change protected home, roles or endpoints.
  - **success:** Project node/port/config edits and central metadata attempts are denied without changing authority.

- **CAP-9** — Central versus local authority (S2-06-FR09)
  - **intent:** Central account/home/credential authority supplies only the identity projection needed for local production.
  - **success:** Same-host tests allow central writes, deny node/project central writes, exclude credential material from projection and retain current token authentication.

- **CAP-10** — Compatible test upgrade (S2-06-FR10)
  - **intent:** Existing test data stays usable through the node ownership increment.
  - **success:** Temporary-database upgrade/restart retains all identities; conflicts block without destructive reset or test-to-production transfer.

- **CAP-11** — Physical-node topology (S2-06-FR11)
  - **intent:** Multiple Runners share one physical ownership and capacity boundary.
  - **success:** Runner/instance identity cannot multiply homes/candidates/capacity; unsupported independent .NET topology is explicitly rejected.

- **CAP-12** — Approved shared content (S2-06-FR12)
  - **intent:** Accounts can consume one approved read-only version while private project data stays isolated.
  - **success:** Two-account contract validation proves shared version access and private project/snapshot/cache denial; edited copies never claim original bytes.

- **CAP-13** — Notification role contract (S2-06-FR13)
  - **intent:** Protected central publication authorizes node-local notification audience and read state.
  - **success:** Same-host contract validation denies forged project/port authority and filters list/detail/count/read by account/home, audience, validity and notice/revision.

## Constraints

- Existing account/project/workspace/run identity, token authentication, .NET, local SQLite/disk, Runner isolation, locks/lease/fencing and snapshot/restore authority remain the foundation; browser/API compatibility is preserved.
- Protected configuration and metadata own node/home/roles; clients and writable projects cannot select them. Unknown or mismatched ownership fails closed without remote reads or reassignment.
- Central account/home/password authority and node-minimal projection must be separated in the same-host contract. Architecture freezes irreversible authority before interfaces; changed security/storage contracts require an Accepted ADR before implementation.
- One production service with multiple Runners is the minimum topology. Independent multi-.NET deployment remains unsupported until physical budgets, locks/fencing and same-role authentication/Data Protection evidence exist.
- Node capacity is counted once; online, policy and measurement validity are separate. S2-03A supplies real measurement; no numeric capacity or timeout is invented here.
- All four companions are normative: identity/persistence, real consumer/role boundaries, shared-content/notification contracts, and FR/AC verification. Their local contract tests do not prove Windows or cross-host operation.

## Non-goals

- Dynamic/user/admin node selection, account or test-project migration, second-node admission, cross-node Workers, distributed SQLite, remote user storage, second object backend or VM isolation product.
- Identity/Direct Mail implementation, second login method, account erasure, new credential authority, knowledge governance/sync, Phase Locator integration, Redis/KV/SignalR selection, full notification product/UI or cross-host notification protocol.
- Rebuilding completed 8-24 capabilities, user Git/GitHub, patch gateways, second ledgers/validators, full frontend or telemetry work, VDD/Quick Dev/Acceptance, deployment or runtime changes in this authoring stage.

## Success signal

All nine approved ACs have current evidence at their declared layer: stable identity and usable upgraded tests; denied forged ownership and disabled-role production; honest physical capacity; isolated approved-source and notification contracts. Completion additionally needs actual Windows Runner/isolation evidence where applicable; same-host contract success cannot certify cross-host behavior. This authoring run executes none of those runtime ACs.

## Assumptions

- Logical persistence/readback names in companions are minimum design choices within approved intent; architecture may refine signatures and installation order while preserving authority, data and compatibility. No product decision is inferred from the uninspected Newrouge repository.
