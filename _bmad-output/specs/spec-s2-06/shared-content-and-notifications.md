# Shared Content and Notification Contracts

Scope: S2-06-FR12/13 and applicable shared revision-6 constraints. These minimum same-host contracts are required now; full knowledge consumer/product and notification UI/transport remain with their owners.

## Approved shared content boundary (AC08)

Existing approval/maintenance facts select a protected read-only version directory. A logical `ApprovedSourceRef` includes approved source identity, concrete version and content hash/manifest reference. It is an allowlisted service reference, never a project-supplied host path or arbitrary URL. Query/copy validates current approval, requested operation, source bytes and account/project visibility before returning content. Missing source/approval/scope, hash mismatch or failed bounded fallback returns unavailable/denial, never a success based on stale cache.

| Data | Authority and permitted use |
| --- | --- |
| Approved knowledge/demo bytes | Existing protected version authority; multiple accounts may read the same approved version. Shared does not mean writable or cross-node user storage. |
| Node shared query cache | Derived, host-owned bounded memory in the one-service baseline; key includes source version/hash, implementation/query version, parameters and visible scope. Authorization is rechecked on a hit. Failure permits only bounded authorized fallback. |
| Private project index/query cache | Account/project/workspace-generation scoped, separate from shared namespaces; no cross-account lookup or shared current/LKG pointer. |
| Copied project resource | Independent editable project content under existing project tools; record actual source/version and operation/run connection when consumed. Edits cease to represent original bytes; global version updates never overwrite user edits automatically. |
| Account home/password, resource commitment, route result, recovery/acceptance | Never cache authority; use existing protected owners. No source update invalidates unrelated unconsuming projects' acceptance. |

AC08 requires a small adapter/contract fixture using one approved version and two accounts: both can consume the same read-only source; neither can designate a private project as an approved source or read the other's project/snapshot/private cache. Demonstrate copy isolation and hash/provenance truth after edits. This is contract validation, not a full new Phase Locator integration. Existing repository Locator is not a project capability and a child invoking a CLI cannot create trusted context.

S2-01/S2-04A/S2-05 own real consumer/query/copy integration; S2-02 owns actual operation provenance; S2-03A/B own measured cache/queue budgets. File-byte caching and small parsed-object caching differ; demo files are not bulk KV contents. Multi-process shared query/KV is optional only after measured need and topology proof. Cache/queue/game budgets remain distinct; caching cannot raise safe concurrency or replace session revocation/locks.

## Notification authority (AC09)

Use protected platform SQLite metadata for the local contract, separate from projects. The following are logical records to make authority/denials testable, not a full S2-04C database/API/UI design or S3-03 protocol.

| Logical record | Writer and content | Reader |
| --- | --- | --- |
| Publication fact | Existing central admin/service authorizes notice identity/revision, body, audience kind (`all`, `node`, `account`) and matching audience IDs, valid-from/until UTC, active/withdrawn state and protected change revision | Approved in-process projection adapter only; production/project cannot author or replace facts |
| Node audience projection | Central-authorized adapter derives matching node-local facts from publication; stores source notice/revision/change reference and current visible status | Restricted node reader; projection is derived, never authority to publish or change permissions |
| Local read state | Node read-state service writes `(account_id, notice_id, revision, read)` for the authenticated matching home/account | Same account filtered list/detail/count and mark-read; no cross-account history/audit product |

The publisher uses existing administrator authority; browser port, node endpoint, ordinary account/project RequestContext or a supplied control-identity string grants no publish/projection-ingest capability. The approved in-process adapter is registered by protected composition and cannot be chosen by project input. There is no new public ingest route, arbitrary endpoint proxy or remote credential protocol in S2-06.

An AC09 contract test must publish through the central capability, derive a node audience projection, query as eligible/ineligible accounts and mark the current revision read. Local publication/projection update is atomic within its protected local transaction; interruption must not expose a mixed revision. A read-state key cannot mark another revision or account read; a new revision has its own read state. Reject project authority attempting central writes or projection replacement even if it supplies a legitimate node ID/port. No credential values enter records/readback.

All list, detail, count and read operations enforce current enabled account, home, local node, audience and validity together. `all`/node audiences include newly activated eligible accounts during the validity interval, without precomputing a permanently frozen recipient list. Known expiry is effective even while refresh is pending. Withdrawn notices are excluded after the protected local update is observed. Notification body is inert content: no command, Agent launch, installation or authorization. Read state does not become user behavior audit or project evidence.

For S2-06 same-host validation, read current protected facts directly/derive synchronously; no remote cursor is needed. Later S2-04C owns full persisted publish/revise/withdraw, inbox/UI and periodic refresh. Later S3-03 owns authenticated service increments, durable change records, atomic projection/cursor, retries/deduplication, offline continuation, epoch/baseline/watermark/retention/UTC decisions and real cross-host evidence. Do not claim these work because local contract tests pass.

Delayed or unavailable future refresh is displayed honestly as stale/pending; known expiration never extends, permissions and project/run results never change, and backlog alone does not block otherwise safe tasks/registration. Do not promise instant offline withdrawal or unlimited history. SignalR/Redis backplane/PubSub could only optimize online refresh, not publication truth or offline recovery. Make/Zapier cannot own node control, permission or dispatch.

## Applicable platform guardrails

Platform shared sources, central facts, node-local projections, private projects and toolchain lifecycle each keep separate authority/current/cache. All file/queue/background paths retain current server authorization, low-privilege Runner isolation, bounded resources and approved networking. A fixed trusted service channel does not grant network access to a game process or project Agent. Arbitrary user Skill/MCP/plugin/software installs, tool markets and automatic approval are excluded.

Existing normal file deletion, usable covering-snapshot recovery, DB-bound validation/evidence and route recovery remain; no recycle bin, per-overwrite backup or guaranteed recovery is added. Execution-boundary reauthorization (S2-05/S2-04A), ordinary run redaction/SLS/Sentry limits (S2-03B) and active-content browser/session/network isolation (S2-05/S2-04B) remain actual release conditions for those consumers. Identity/Direct Mail and minimal soft-delete remain before formal account-product opening, even on one node; S2-06 uses existing test tokens without claiming those products complete.
