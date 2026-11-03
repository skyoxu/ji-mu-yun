# S2-06 PRD Addendum: Brownfield Evidence and Downstream Design Handoff

Date: 2026-10-28. Repository baseline: `25580d700da91d2702fd234a024a616d55419f90`.

This companion preserves technical depth outside the capability PRD. It is not a SPEC, accepted architecture delta, implementation plan or acceptance receipt. Audit/override decisions live in the official `.memlog.md`.

## 1. Bounded current-source observations

The current checked branch and HEAD match the caller's fixed baseline. Targeted static reads of `PhaseA.Platform/Data/AccountSnapshot.cs`, `ProjectSnapshot.cs` and `RunSnapshot.cs` show existing account/project/run identity and project/account ownership, but no explicit account home or actual-node reference in those records. `Security/RequestContext.cs` enforces account authorization; it does not express a node-home check. These are gaps to close compatibly, not evidence that current authorization must be replaced.

`Configuration/PhaseAPlatformOptions.cs` contains access addresses and a development/test/production service-environment state. That environment state does not express the proposed logical entry/production roles. `Program.cs` currently registers project creation, initialization recovery and several queues/services without the proposed role split. The bounded read supports the need for a dispatch inventory; it is not a complete consumer audit or proof of runtime behavior.

`Data/SqliteMetadataSchema.cs` already provides additive column installation inside schema initialization. Existing SQLite, account/project/workspace identities, Windows Runner registration and isolation, lease/fencing, snapshot/restore and quota foundations are reuse points under Accepted ADR-0035/0036/0038/0061. A new logical node reference is not a second workspace ID or permission authority.

Route advice's earlier preflight/knowledge limitations are historical preparation statements. This run performed actual native resolver activation and a new read-only matched query; that only establishes knowledge consumption, not S2-06 implementation or Windows validation.

## 2. Logical interfaces to freeze downstream

The following names are logical references from the approved sources. SPEC chooses location and field shape after naming the producer, authority and consumers; the PRD does not require each field on every record/sidecar.

| Interface | Required meaning | Design owner and revisit condition |
| --- | --- | --- |
| Node configuration | Stable physical `node_id`, enabled logical roles and mutable endpoints with separate login/workbench/active-content purpose | SPEC + architecture, before schema/config contract freeze; distinguish environment from logical role and define missing/conflicting config rejection. |
| Account-home persistence/readback | Existing `account_id` maps to one server-owned `home_node_id`; current test binding survives restart | SPEC, before implementation planning; choose additive store/DTO adaptation and migration/recovery behavior without new identity authority. |
| Actual-node boundary | Protected node reference resolves project/package/snapshot/run operations and denies unknown/mismatched ownership | SPEC, before implementation planning; enumerate HTTP, readback, queue, recovery, restore/package and publication consumers actually touched. |
| Central/node authority | Central account state/home/password authority; minimum protected local identity projection and local project/execution authority | Architecture first, then SPEC, before storage or dispatch decisions; same-host tests must prove permitted writes and denials without claiming a cross-host protocol. |
| Capacity/readiness | Physical-node online status, accept-new-account policy, capacity/readiness reference and measurement validity | SPEC defines interface now; S2-03A measures and proves commitments later; no synthetic measured capacity or new resource thresholds. |
| Role dispatch | No ordinary creation/execution production when production responsibility is closed | SPEC + architecture, before implementation planning; inventory service/DI/hosted recovery/queue/dispatch paths and define startup and in-flight transition handling under existing cancellation/cleanup rules. |
| Process topology | `instance_id` diagnostics cannot multiply physical capacity/home/candidates | Architecture + S2-03A, before enabling independent .NET instances; shared physical budgets, locks/leases/fencing and same-role authentication/Data Protection evidence are prerequisites. Otherwise reject unsupported topology. |
| Shared content | Approved version authority stays with existing maintenance; shared source/cache scope stays outside private projects | SPEC, at interface design; reuse bounded query/approved-copy consumers and authorization scope, no new publication/sync governance. |
| Notification roles | Protected central publication facts, authorized node audience projection and local notice/revision read state | SPEC/architecture now for authority contract; S2-04C for single-node product; S3-03 before real cross-host exposure for auth/cursor/retry/baseline recovery. |
| Test migration versus production initialization | Additive test preservation now; future distinct initialization without test data or secret reuse | SPEC defines temporary-database compatibility cases now; operator release work later owns production action and evidence. |

These are implementation design obligations, not unresolved product choices or permission to run later workflows. A downstream human scope decision is needed only if the fixed requirements cannot be met compatibly; report that contradiction before choosing an alternative.

## 3. Deferred mechanism detail and guardrails

Do not select columns versus tables, enum/error values, service class interfaces, protocol transport, cache/KV product or topology from a generic document example. Preserve existing DTO/API compatibility and use accepted bounded status/error contracts. A live/destructive repair or change in auth/runtime/security policy still needs its repository authorization and accepted ADR path.

A single node service may dispatch multiple Runners under existing Windows boundaries. Multiple independent .NET services are a different topology: process-local caches/limits are not shared coordination, `AddDistributedMemoryCache` is not an actual cross-process store, and a KV alone does not prove resource locking or credential revocation. No independent multi-service topology is selected by this PRD.

Shared approved resources stay in protected read-only version locations under existing maintenance. Copied resources become editable project content; version provenance must not claim unchanged original bytes after edits. Query-cache keys and bounded fallback mechanics belong to their owning S2-01/S2-03A/B consumers. Cached results cannot replace password/home/commitment or acceptance authority.

S2-06 notification contract tests need enough protected facts/projection/read-state scaffolding to prove roles and denials. They do not authorize building the S2-04C inbox/publisher or S3-03 transport. Later product behavior retains audience/expiry/revision/read filtering, periodic refresh and local persistence; later cross-host design retains durable changes, atomic cursor/projection, bounded retention, retry/deduplication and baseline recovery. SignalR/Redis transport is optional refresh optimization only.

The existing account/token path is usable for current step2 testing. Identity/custom store, Direct Mail password recovery and minimal account soft-delete policy are a separate formal-account product prerequisite before formal single-node opening, independent of when multi-node work happens. Do not implement them in S2-06 or use their later package number to postpone required authorization at current execution consumers.

## 4. Validation boundary and handoff

PRD authoring checks only requirement coverage, source identity, links, memlog reconciliation and scope consistency. Runtime implementation must later exercise the nine ACs with temporary databases and workspaces, actual HTTP/background consumers and real Windows Runner/ACL boundaries. A selected independent-.NET topology needs real shared coordination/auth evidence. A later real second host needs its own authenticated protocol, offline/restart and mismatch evidence; same-host tests do not establish it.

Normal project deletion, snapshot coverage limits, account/project isolation, controlled network/tool use, execution-boundary reauthorization, ordinary run-record redaction and browser active-content isolation stay with their established package owners. This package adds the shared physical ownership/role contract without claiming those separate opening conditions are met.
