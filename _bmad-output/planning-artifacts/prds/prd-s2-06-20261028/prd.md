---
title: "S2-06: Stable Node Identity, Ownership Contracts and Test Role Boundaries"
status: final
created: 2026-10-28
updated: 2026-10-28
package: S2-06
source_revision: 5
repository_baseline: 25580d700da91d2702fd234a024a616d55419f90
---

# PRD: S2-06 Stable Node Identity, Ownership Contracts and Test Role Boundaries

## 0. Document purpose and authority

This PRD defines one brownfield platform capability for Ji Mu Yun. It gives PM, SPEC and architecture authors a fixed product boundary before implementation planning: stable physical ownership, server-owned account home, explicit entry/production responsibilities, and the minimum capacity, shared-content and notification contracts those responsibilities need. It preserves the upstream IDs S2-06-FR01 through S2-06-FR13 and S2-06-AC01 through S2-06-AC09. These are upstream requirement IDs, not generated VDD IDs.

The approved inputs are the complete Library text exports under `docs/requirements/s2-06/source/`: `step2/S2-06/S2-06-requirements.md` (Library version 2, document revision 5, 2026-10-07), `00-shared-scope-and-contracts.md` and `01-dependencies-and-delivery.md` (both Library version 5, document revision 6, 2026-10-08). They are text exports; each is one byte shorter than its Library metadata size and is not represented as a byte-identical downloaded original. The original inputs name historical code baselines; current repository observations in this PRD are limited to main/HEAD `25580d700da91d2702fd234a024a616d55419f90` on `feat/s2-06-preparation-20261028`. Newrouge is an upstream reference, not inspected implementation evidence.

Accepted ADR-0035/0036/0038/0061 and their inherited local SQLite, account-token, Runner, workspace, snapshot and lease/fencing boundaries remain authoritative. ADR-0044 keeps knowledge projections and caches derived. `addendum.md` holds technical design handoffs and source observations. Reconciliation notes account for each source separately. This document finalizes requirements authoring only; it is not code, migration execution, runtime acceptance, release authority or proof that S2-06 works.

## 1. Vision and problem

An account's projects must stay on one physical production node even when its endpoint or a service process changes. The current service has reusable account/project/run identities and local execution foundations, but those identities do not yet express stable physical-node ownership or the proposed logical role boundary. A hostname, port, browser cache or username cannot serve as that ownership authority.

S2-06 makes the current single-node test arrangement explicit while preserving a compatible contract for later separated deployment. The logical entry role serves registration/login, home routing and administration. The production role serves the ordinary workbench, local projects and Runner. Disabling production responsibility must stop ordinary project production in background consumers as well as HTTP routes. An ownership mismatch is a refusal, never an implicit remote read, execution or relocation.

The trade-off is deliberate: current test identities remain usable through additive changes, while dynamic placement, real cross-host exchange and production account rollout stay outside this package. The result should let later packages consume a stable scope without rebuilding existing identity, Runner or storage capabilities.

## 2. Target users and jobs

Platform operators need to configure a stable physical node and the enabled logical roles, change access addresses without recreating accounts or projects, and see whether a supported topology is within the proven test boundary. Existing authenticated test-account users need their projects, packages, snapshots and execution to remain usable under the same identity after restart and additive migration. Platform service consumers need an authoritative account-home and role decision rather than a browser-selected node or an implicit process default.

This is a technical capability PRD. The inputs supply no narrated human sessions, so named persona journeys are omitted; the acceptance scenarios describe observable operator and service behavior. No new workbench, node-picker or notification-inbox experience is specified here.

## 3. Glossary

- **Physical node / `node_id`**: the stable physical production ownership boundary. A process, Runner count, endpoint or browser port does not create another physical node.
- **Process instance / `instance_id`**: an optional process diagnostic or coordination identity. It grants neither account ownership nor additional capacity.
- **Logical entry role**: registration/login, authoritative account-home routing and administrator entry responsibilities; it has no ordinary workbench or ordinary project execution responsibility.
- **Production role**: ordinary workbench, node-local projects and Runner responsibilities. Logical role is distinct from the existing development/test/production service-environment state.
- **Endpoint**: a mutable access address, independent of `node_id` and account/project/run identity.
- **Account home / `home_node_id`**: the one server-owned physical-node assignment for an existing `account_id`; requests cannot select or overwrite it.
- **Actual node**: the protected physical-node ownership used when resolving project/run reads, writes and execution; its logical reference need not be copied to every artifact.
- **Central account authority**: the logical authority for account state, unique account home and password authority. Co-location in tests does not merge it with node project authority.
- **Local identity projection**: the minimum protected account identity/state needed by a production role; it cannot independently reassign account home or create a second password authority.
- **Capacity contract**: a node-scoped interface describing online status, acceptance policy for new accounts, capacity/readiness references and measurement validity. S2-03A supplies real measurement.
- **Approved shared version**: an existing approved, read-only knowledge/demo version distinct from user projects, snapshots and private caches.
- **Notification projection**: the node-local authorized audience view and local read state derived from protected publication facts; it is not a project file or a transport identity.

## 4. Features and functional requirements

### 4.1 Stable identity and account home

The service uses protected physical ownership independently of its access addresses. Existing account/project/run/workspace identities remain the identity backbone.

#### S2-06-FR01: Stable node and endpoint purposes

The operator can configure a stable `node_id` and logical role. Endpoints remain mutable. The contract distinguishes central login, production workbench and user active-content origins; user active content must not carry platform sessions.

Testable consequences:
- Restart or endpoint/port change does not recreate node, account or project identity.
- Account ports, browser caches and usernames are never consulted as account-home authority.
- Login/workbench/active-content purposes are distinguishable in the configuration contract. Defining the origin boundary here does not certify the browser isolation implemented by S2-05/S2-04B.

#### S2-06-FR02: One server-owned account home

The service owns the unique `account_id` to `home_node_id` meaning: all of the account's projects, packages, snapshots and execution stay on its physical node. A user request cannot override that home.

Testable consequences:
- Client-supplied, missing or forged ownership cannot authorize a different node's project operation.
- Ownership mismatch or unknown required ownership denies the affected operation; it never causes a remote read/run or silent reassignment.
- Local capacity shortage blocks new work according to its existing admission contract; it does not silently move account data or execution.

#### S2-06-FR03: Persistent single test-node binding

The server binds current step2 test accounts to the unique test node and persists a readable account-home binding using a contract compatible with later step3 consumers.

Testable consequences:
- Existing test accounts read back the same binding after restart and incremental migration.
- Readback explicitly identifies the supported single-node test scope.
- No response or documentation claims that automatic placement or multi-node registration has been implemented.

#### S2-06-FR04: Actual-node enforcement

Project reads, writes and execution retain protected actual-node/ownership checks alongside existing account/project authorization.

Testable consequences:
- A mismatch between account home, project/run ownership and the executing physical node refuses the operation before file access or execution.
- Endpoint changes leave historical project/run identities intact.
- The mismatch path does not open another node's files or SQLite database to complete the request.

### 4.2 Role boundaries and protected authority

Entry and production responsibilities may be tested on one host. Their authority and dispatch responsibilities must remain separable for production configuration.

#### S2-06-FR05: Entry and production responsibilities

The logical entry role carries registration/login, account-home lookup/routing and administrator entry. The production role carries the ordinary workbench, projects and Runner. Tests may enable both logical roles on one host; production configuration separates them.

Testable consequences:
- An entry-only configuration retains permitted entry/admin responsibilities while ordinary workbench/project execution responsibilities are unavailable.
- Existing token authentication can support the current test contract without claiming that future Identity/password recovery is delivered.
- Co-location is labeled a test arrangement, not a verified production split or cross-host protocol.

#### S2-06-FR06: Role-aware background production

Closing a production role removes its corresponding project-creation/execution production responsibilities, including residual dependency-injection registrations, recovery workers, queued dispatch and background consumers.

Testable consequences:
- Entry-only startup and dispatch cannot start ordinary project creation or execution through a default service or consumer.
- Already queued or recovered ordinary work cannot bypass the current role boundary. Existing cancellation/cleanup and authorization obligations remain in force; SPEC must identify the actual consumers and transition behavior.
- Login/routing/admin activity does not implicitly acquire ordinary project-scheduling authority.

#### S2-06-FR08: Project-independent protected configuration

Account-home, node-role and endpoint authority remain in protected service configuration/metadata outside writable projects.

Testable consequences:
- Editing project files, project AGENTS/Skill copies, `node`/`port` fields or process diagnostics cannot select another node or change account home.
- Project Agent/file/Runner paths cannot modify central account metadata, credential authority or protected configuration.
- All applicable write and background paths retain the same existing account/project boundary and low-privilege execution controls.

#### S2-06-FR09: Central and node authority separation

Central account authority owns account state and unique home. Node project authority owns its local projects, files, packages, snapshots and execution. A production role holds only the necessary local identity projection; it cannot independently modify home or duplicate central password authority.

Testable consequences:
- Same-host contract tests distinguish authoritative central writes from node projection reads and deny unauthorized production/project writes to central home/password authority.
- Local identity projection is demonstrably limited to its authorized use and cannot become an independently mutable account-home/password source.
- Later cross-host projection exchange uses a service protocol, not a node opening the entry host's SQLite file. The current test demonstrates authority separation only; transport authentication and recovery need later evidence.

### 4.3 Node-scoped capacity and compatibility

#### S2-06-FR07: Minimum capacity interface

Service consumers can read a minimal capacity contract with `node_id`, online status, policy for accepting new accounts, capacity/readiness references and whether the measurement is valid. The contract consumes later real S2-03A capacity without making S2-06 depend on S2-03A implementation first.

Testable consequences:
- A reader can distinguish online status, acceptance policy and measurement validity; online alone is not measured readiness or account-placement permission.
- Unmeasured test state is represented honestly and cannot be reported as measured real capacity.
- S2-06 neither invents resource limits nor claims registration/health negotiation or automatic placement. Those actual protocols remain step3 work.

#### S2-06-FR10: Additive test migration and later cutover

The S2-06 increment preserves existing test data usability and identity consistency through additive migration. Production starts with a separate initialization and no migration of test accounts/projects or reuse of test secrets.

Testable consequences:
- Temporary-database migration/restart tests retain existing account/project/run identity and the persisted test home.
- An incremental test migration does not reset existing test identities to simulate a production cutover.
- Production initialization remains a future separately authorized operation; this package does not create a test-to-production transfer plan or execute a reset.

#### S2-06-FR11: Physical-node counting and process topology

Multiple Agents, Runners or supported .NET process instances on one physical node share its ownership and capacity boundary. Optional `instance_id` exists only for process diagnostics/coordination.

Testable consequences:
- Changing process identity or Runner count leaves account home/project identity unchanged and does not multiply capacity, registry candidates or account assignments.
- A topology of independent .NET instances cannot be enabled merely because each process has a local concurrency limiter or cache.
- An unsupported topology is explicitly rejected until shared physical budgets, locks/lease/fencing and same-role authentication state including required Data Protection keys are proven. S2-03A owns measurement and shared resource commitments; this contract does not select a coordination backend.

### 4.4 Shared content and notification authority

#### S2-06-FR12: Shared approved content without shared user storage

Approved knowledge/demo versions may be provided read-only on each node using existing maintenance/approval mechanisms. Platform shared sources and node query caches remain separate from user project data.

Testable consequences:
- Two accounts can consume the same approved read-only version without gaining access to each other's projects, snapshots or private caches.
- Shared access does not cause user files or snapshots to be stored across nodes; any copied project content is an independent editable project copy and global updates do not overwrite it.
- Caches grant no permissions and store no authoritative account home, password, resource commitment, route result or recovery data. Queries stop if authorization/private scope cannot be established.
- No new publication governance, knowledge synchronization platform or source-wide project invalidation is introduced.

#### S2-06-FR13: Notification authority and projection roles

The logical central administrator and protected publication facts authorize notifications. Production roles consume the authorized node audience projection and local read state through approved service paths.

Testable consequences:
- Same-host contract tests permit only the approved publisher/service authority to supply protected projection facts; a project identity, browser port or forged control identity cannot do so.
- Notification body/change facts, projections and read state are protected platform metadata outside projects. The role contract preserves account/home filtering for list/detail/count/read state, audience/validity and notice/revision read semantics.
- Notification content cannot execute commands, start Agents, install capabilities or grant permissions. Projection/cache state cannot replace protected publication or local read authority.
- Tests and readback explicitly distinguish the local contract from cross-host authentication/cursor recovery. Full inbox/publish/revise/withdraw UI and single-node product behavior belong to S2-04C; cross-host exchange and recovery belong to S3-03.

## 5. Cross-cutting constraints

### Security and compatibility

Existing `account_id`, project/workspace/run/artifact/correlation identity, RequestContext, account-token authorization, Runner registration, ACL/Job Object isolation, leases/fencing, snapshots, restoration and quota are reused. Existing API routes, fields, status semantics, auth behavior and artifact paths remain compatible unless a separately approved compatibility plan says otherwise. New schema changes are additive; tests use temporary databases/workspaces and never live state.

The toolchain control plane, Phase service authority and user project layer stay separate. Project content is untrusted and may narrow but never expand service permissions. No arbitrary user/Agent installation of software, external Skills, plugins or MCP is introduced. Approved platform service channels do not grant project network access. Current execution-boundary reauthorization and run-record redaction obligations owned by S2-05/S2-04A and S2-03B remain release conditions for their actual consumers; S2-06 does not replace them with a second authorization or validation platform.

Browser-visible readback is account-scoped or explicitly admin-only, redacted and limited to logical references. It does not leak credentials, secret configuration, raw host paths or another account's existence. Error/status details must fit existing bounded contracts; SPEC chooses compatible mappings rather than introducing unsupported status values.

### Locality and resource authority

Local SQLite and node-local project storage remain. Distinct nodes do not share a SQLite file as a network database. Node capacity, service cache/queue budgets and game-task budgets remain distinct; a cache or KV is neither a resource lock nor session-revocation authority. No threshold, parallelism increase or production availability target is invented in this PRD.

### Evidence and failure behavior

Wrong/missing ownership, forbidden role, unproven topology and unauthorized projection use fail closed for the affected operation. A readback, assistant statement or copied evidence file cannot authorize execution or declare acceptance. Existing machine consumers and database-bound artifact evidence remain authoritative. Failure history is append-only. Windows execution/ACL/isolation and real multi-process or multi-host evidence must be labeled separately from static inspection and same-host contract tests.

Notification delay cannot alter user permissions or project/run results. Later notification product/synchronization implementations must keep known expiry effective, report stale/pending refresh honestly, and avoid promising immediate offline withdrawal or unlimited history. Notification backlog alone does not block otherwise safe tasks or registration. Those behaviors remain with S2-04C/S3-03 rather than expanding S2-06 implementation.

## 6. Scope and non-goals

The delivered increment is stable node/role configuration, persistent single test-node ownership, compatible actual-node checks, role-aware current test wiring and the minimum capacity/shared-content/notification authority contracts. It is not a new account system or storage/Runner rebuild.

Explicit exclusions:
- User-selected nodes, administrator manual assignment, dynamic account placement or migration, test-project relocation, arbitrary cross-node Workers and real second-node admission.
- Distributed SQLite, database replacement, a second object-storage backend, cross-node user project storage or a full VM isolation product.
- ASP.NET Core Identity/Direct Mail implementation, OIDC or another login method, account physical erasure or a complete admin product. Formal single-node password/recovery and minimum account soft-delete policy must still be delivered before that formal account product opens; step3 naming does not waive that condition.
- Knowledge publication/evaluation/upgrade governance, a new cross-node knowledge platform, forced Redis/Upstash, SignalR or backplane selection.
- Full notification product/UI or cross-host cursor/retry/baseline protocol; these remain S2-04C and S3-03.
- User Git/GitHub, patch gateways, second ledgers/validators/state authorities, full frontend rewrite, Godot runtime analysis, whole-platform telemetry and the already completed 8-24 capabilities.
- VDD, Quick Dev, implementation, live migration/reset, deployment, push, PR or commit in this authoring stage.

Normal game-file deletion and recovery from existing usable snapshots remain unchanged: no recycle bin, per-overwrite backup or guaranteed recovery without a covering snapshot. Production HTTPS/session safety remains a before-release condition outside this planning increment.

## 7. Dependencies and downstream handoff

S2-06 depends on existing account/project/metadata foundations and may be the first step2 package. It defines the node/capacity interface; S2-03A later supplies the real read model. There is no implementation cycle between those packages. S2-03A/B, S2-01/02, S2-04A/B, S2-05 and S2-04C consume its stable scope at their relevant boundaries. This PRD does not load or redefine all seventeen packages.

SPEC must choose the smallest compatible persistence, readback and dispatch changes and identify every actual creation/execution consumer. Architecture must first freeze irreversible central-versus-node authority, then cross-cutting ownership/topology rules, runtime role dispatch and feature interfaces. Any new ADR required for changed authentication, ownership, storage or execution boundaries must be accepted before implementation relies on it; a Proposed ADR is not code authority.

A production rollout is separate from successful test migration. The source requires formal initialization and test separation without test-data transfer or test-secret reuse. This PRD supplies no rollout authorization or completed Windows/cross-host claim.

## 8. Success and acceptance

The success criterion is complete, current evidence for the nine approved scenarios, with no unsupported scope claim. The target is all nine demonstrated at their stated layer before S2-06 implementation is declared complete; this authoring run has executed none of those runtime scenarios. No market, usage, latency or capacity target was supplied.

Counter-metrics: increasing apparent node count through process count, reporting unmeasured capacity as valid, or broadening a same-host result into cross-host success is failure even if more requests appear to succeed. Existing account/project usability and isolation must not regress to produce a passing role test.

| Scenario | Required setup/action | Observable result and evidence boundary |
| --- | --- | --- |
| S2-06-AC01 | Two logical roles on one test host and one physical test node; existing authenticated project use | Stable identity, explicit responsibilities and usable current projects; bindings and role behavior are observable. This proves the same-host test configuration only. |
| S2-06-AC02 | Change endpoint/port and submit forged node/home data through browser/request paths | Node/account/project identity stays unchanged; wrong-home read/write/run is denied before access/execution. A rejected request does not route data to another node. |
| S2-06-AC03 | Incrementally migrate a temporary existing test database, restart, then read identities/home/projects | Test data remains usable; original identity and persisted home remain consistent, with no destructive reset. |
| S2-06-AC04 | Disable production responsibility on the entry role; exercise HTTP and queued/recovery/background paths | Ordinary creation/execution consumers do not produce work; allowed login/routing/admin duties remain. Merely hiding an endpoint is insufficient. |
| S2-06-AC05 | Modify project node/port configuration and attempt central account/credential access | Service-owned home, roles and password authority remain unchanged and inaccessible through project authority; production local projection cannot independently change them. |
| S2-06-AC06 | Run/read the contract before real node registration/health/transport exists | Readback labels the single-node test boundary and measurement validity honestly; no automatic multi-host or production-ready claim. |
| S2-06-AC07 | Multiple Runners or an actually supported .NET topology on one physical node; change process diagnostic identity | Home/project identity remains stable and node/capacity/candidates are counted once. An unsupported independent-.NET topology is explicitly rejected until coordination/auth evidence exists. |
| S2-06-AC08 | Two accounts consume one approved knowledge/demo version; attempt to expose one account's project as shared source | Approved source remains read-only/versioned; project/snapshot/private-cache isolation holds and no cross-node user file storage is introduced. |
| S2-06-AC09 | Same-host central/production notification publication and local audience contract; forged project/control identity/port | Protected publication versus projection/read-state roles are observable; only approved service authority can consume protected projections. Result does not certify S3-03 cross-host sync. |

Implementation evidence must identify the exact HEAD/diff, actual consumer paths and current failure results, with separate targeted code tests, Windows native isolation/Runner evidence and any selected multi-instance evidence. Existing tests from earlier capabilities and this document's checks cannot substitute for that evidence.

## 9. Open questions and assumptions

No unresolved product decision is required to hand this frozen S2-06 scope to SPEC and architecture. No inferred product requirement, numeric threshold, invented journey or selected coordination/storage topology is used here. Downstream design tasks are recorded with owners and revisit conditions in `addendum.md`; they are not assertions that those mechanisms exist.

The accepted exclusions remain binding. If downstream design discovers a contradiction in authority, an incompatible API change or a topology that cannot satisfy the contract, it must surface that decision gap before implementation. It may not silently weaken an FR/AC or promote future cross-host behavior into current scope.
