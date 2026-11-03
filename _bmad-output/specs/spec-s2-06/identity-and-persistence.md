# Identity, Authority and Persistence Contract

Scope: S2-06-FR01/02/03/04/07/08/09/10/11. All interfaces below are required design contracts, not claims of existing code. Baseline: `25580d700da91d2702fd234a024a616d55419f90`.

## Authority first

| Owner | Authoritative operations | Permitted consumers and explicit denial |
| --- | --- | --- |
| Logical central service | Current account enabled state, credential verification/revocation, unique account home, administrator control | Existing token verifier and central account administration only. Neither production-local projection nor project identity can write account home/state/password/token hashes. |
| Physical production node | Own projects/files/packages/snapshots/runs and execution; local projection/read state | Restricted project/projection service contracts, current RequestContext and actual-node check. Cannot open another node's files or central host SQLite. |
| Existing knowledge control plane | Approved shared source/version facts | Read-only approved source adapters; cache/project copies cannot publish or approve a version. |
| User project | Editable game content and independent copied resources | Existing authorized project tools/Runner only. AGENTS/Skills/config/evidence copies are untrusted and cannot elevate service authority. |

Co-located tests retain one trusted composition root and existing local SQLite technology. Logical central and node stores may initially share the protected local metadata database; this is neither OS isolation between service components nor a cross-host data protocol. The central adapter alone receives account writer/credential-store capability. Production-facing components receive restricted local project/projection contracts; injecting the unrestricted central writer/connection into those components is prohibited. A node reader cannot bypass the adapter by using raw SQL. Architecture must make this dependency boundary executable and testable before implementation.

Current central authentication continues to resolve existing token hashes and produce the existing RequestContext; local production receives that verified context, never a copied credential authority. Dispatch/publication reauthorization invokes the trusted central adapter in process for this test arrangement. It cannot authorize from a stale local enabled flag alone. There is no second password store, token issuer or new network login/projection protocol. Later distinct-host exchanges require separately authenticated service contracts, not a network SQLite mount. Formal Identity/password recovery remains a separate before-opening condition.

## Protected configuration meaning

| Logical field | Meaning and validation |
| --- | --- |
| `node_id` | Explicit nonempty opaque, ordinal physical production identifier; initialized once and compared to persisted local binding. Never derive it from hostname, port, endpoint, username or Runner/process ID. Entry routing references this same one test production node. |
| `enabled_roles` | Explicit set of `entry` and/or `production`; logical responsibility, separate from existing `PhaseServiceState=development/test/production`. No implicit production fallback. Co-location of both is test-only. |
| `topology` | `single_service` baseline: one production service owns the node's queues/budgets; multiple registered Runners allowed. A second independently scheduling .NET service is unsupported unless the later proof gate is met. Two role adapters within that service do not multiply capacity. |
| `login_endpoint`, `workbench_endpoint`, `active_content_origin` | Protected mutable purpose references. Login is central entry, workbench is production, active content is untrusted and receives no platform session. Existing public URL HTTPS rule stays. No caller endpoint chooses a node. |
| `accept_new_accounts` | Explicit operator acceptance policy; false is refusal of new account admission, not reassignment or deletion of existing accounts. Does not override capacity validity or existing project admission. |
| `instance_id` | Optional diagnostic/coordination value only. Change/restart has no home or capacity effect. |

Before ordinary production is registered, reject missing/blank node identity, missing/unknown roles, physical binding conflict, unsupported topology, or an active-content session origin collision. Distinct origin references alone do not prove browser isolation: S2-05/S2-04B must verify all active entry points before opening them. Endpoint edits are validated independently and never update ownership. No live bind address or runtime secret is selected by this document.

Roles are startup configuration. Changing them requires controlled stop/restart; no hot role-switch API is specified. Entry-only startup must not construct ordinary production consumers. Formal production role separation/init is future authorized release work, not enabled by setting `PhaseServiceState`.

## Minimum persistence choice

Use the existing protected local SQLite metadata and additive installation pattern in `SqliteMetadataSchema.InitializeAsync`; no replacement database or duplicate identity registry.

| Logical record | Minimum persisted data | Owner / readback |
| --- | --- | --- |
| Local node binding singleton | Stable `node_id`, binding version, initialization scope | Trusted startup authority; admin diagnostic only. No capacity multiplier per service instance. |
| Existing accounts | Add nullable-at-install `home_node_id`; one value per existing account | Central account adapter alone writes once for this test increment; trusted home reader exposes only current self or explicit admin scope. |
| Existing projects | Add nullable-at-install `node_id` (actual physical owner) | Node metadata adapter sets it on creation from protected local identity and resolved account home. Never supplied by browser/game project. |
| Local account projection | `account_id`, `home_node_id`, enabled-state projection, authority revision | Central adapter materializes in protected platform metadata; node reader can read only needed local rows. No username/password/hash/token/recovery secret is copied. Missing/stale revision requires central refresh or denial. |
| Existing runs/packages/snapshots | Existing project/account/workspace and package/snapshot binding | Actual node resolves through protected project row; do not stamp node into every run/manifest/sidecar. Existing identity and content hashes stay stable. |

Projection revision is a monotonically changing local central-account fact used to detect stale state; it is not a new authentication system. Account/home/projection update commits together in the same local SQLite transaction. Disable/revoke still uses existing central credential behavior and execution-time checks. Home mutation/reassignment after binding is unsupported; reject rather than update it through this increment.

## Additive test binding and recovery

1. Validate explicit unique test node and protected existing database/workspace boundary. Install additive columns/records in the existing schema transaction. Preserve every account/project/workspace/run ID and all historical receipts.
2. Bind legacy null homes to that node only in the explicit single-node test migration. Verify each project references its real account and valid registered workspace; bind null project owner to the same node. Materialize minimal projections in the same transaction. Do not guess from files, URLs or browser fields.
3. A non-null different binding, orphan owner, invalid workspace registration or conflicting existing project owner aborts affected migration/production startup. No overwrite, destructive reset, silent reassignment or automatic cross-node repair. Preserve evidence for authorized repair.
4. Transaction interruption rolls back; restart safely repeats missing additive installation and verifies completed bindings. Existing valid non-null values are invariant. A role-only entry host cannot bootstrap ordinary projects to repair a mismatch.
5. Later reads/dispatch fail closed for unresolved null/missing homes or actual owner. New accounts bind only through central service to the one configured test node; capacity policy cannot invent future dynamic allocation. New project writes require the equality chain below.

No new production migration program exists. Future production starts separately, without moving test accounts/projects or reusing test secrets. No snapshots roll back account authority, protected node binding, Windows identity or database history.

## Actual-node contract

For an authorized operation, resolve `RequestContext.account_id -> central home -> protected local projection -> project.account_id/project.node_id -> protected configured/persisted local node`. Require matching owner and one node across that chain before resolving any filesystem location. Run/package/snapshot operations additionally follow their existing protected project/workspace/manifest binding. A token admin role does not imply cross-node file access.

Re-evaluate current role and this chain at admission, queued dispatch, protected file read/write and publication/activation boundaries. Preserve existing current-credential checks, workspace generation checks, project locks, fenced lease and route recovery. Cache hits, artifact JSON, RequestContext supplied by a project or an endpoint label cannot substitute for current authority. Missing/conflicting data denies the affected operation; there is no remote fallback.

## Readback and compatible failures

Extend existing authenticated `GET /api/session` additively with an `ownership` object: `homeNodeId`, `nodeId` (actual local production node reference), `scope: single_node_test`, enabled logical roles and the capacity summary below. Preserve existing authenticated/accountId/username/role fields and auth semantics. Resolve self from authenticated identity only. A home mismatch reports safe unavailability rather than another node's endpoint/details. Admin node diagnostics use an explicit admin-only service read contract; no new public registry or node selector.

Capacity summary has `nodeId`, `online`, `acceptNewAccounts`, `measurementValid`, nullable `capacityRef` and `readinessRef`. `online` means local service availability only. Policy true plus online true never means measured readiness. Until S2-03A supplies real current measurement, `measurementValid=false`, references are null and no numeric capacity is emitted. These fields do not replace existing per-service creation/concurrency budgets or enable placement; unproved readiness cannot admit a new placement. Invalid/unavailable references cannot be converted into synthetic success.

| Condition | New response mapping / compatibility rule |
| --- | --- |
| Unknown request node selector/config shape | `400 validation_failed`; user fields never affect ownership. Existing DTOs that ignore unknown fields may keep that behavior if no authority is gained. |
| Missing/revoked credential | Existing `401 authentication_required`. |
| Wrong account, node-home or prohibited role | Existing route's safe `403 forbidden` or `404 project_not_found` convention; do not reveal cross-account existence. |
| Self binding not initialized / inconsistent | `409 conflict` for an authorized self operation; admin diagnostic carries a safe bounded reason. No file access. |
| Local role/dependency unavailable | `503 service_unavailable` when appropriate to existing surface; static entry-only ordinary operations use the denial above. |
| Missing/conflicting startup config/topology | Fail startup/production registration with safe diagnostic; no fabricated HTTP success. |

New API errors use `{code,message,details?,requestId}`; details are redacted logical operation references. Existing caller-visible statuses/envelopes, including package-specific busy/isolation errors, are preserved. No unsupported run status is added: keep existing queued/running/terminal states and legacy `cancel` compatibility where already used. Browser/private/admin readbacks and errors remain `no-store`; never expose token material, host paths or secret configuration.
