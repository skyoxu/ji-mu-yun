# ADR-0044: Knowledge Projection Authority And E2 Hosted Context Envelope

- Status: Accepted
- Date: 2026-07-25
- Decision scope: Phase A/B knowledge projection, context assembly, and E2 hosted dispatch envelope

## Context

The Phase platform needs deterministic knowledge projections and a run-bound context envelope for Hosted LLM/Codex execution. A projection can improve retrieval without becoming a new instruction authority, and an E2 envelope must bind the assembled context to the route, account, project, workspace, snapshot, policy, and dispatch. The platform already has shared LLM/Codex entrypoints in ADR-0037 and evidence/readback contracts in ADR-0038. Duplicating either contract would create competing authority.

## Decision

### 1. Knowledge authority

- Knowledge Projection is always `derived_cache`.
- A projection may return candidates, source references, hashes, ranking evidence, and provenance. It may not override Accepted ADRs, `AGENTS.md`, current source, current runtime facts, route contracts, database authority, or the latest live acceptance blocker.
- Projection, Query, Context Assembly, Manifest, and runtime evidence carry four explicit dimensions: `Domain Scope`, `Per-Domain Visibility`, `Lifecycle Instance`, and `Enforcement Level`.
- The four Domains are `toolchain`, `phase`, `workspace`, and `marketplace`. Cross-domain traversal is an explicit server policy closure, not an implicit query behavior.
- Repository Source, Repository Template, Project Instance, and Run Artifact View are separate lifecycle instances. Their baselines, caches, namespaces, current pointers, and LKG pointers must not be shared. Project Instance data is account/project/workspace-generation scoped.
- Server-owned Route Policy, Published Skill, Account Capability, and Global Scope registries are the permission trust roots. Effective permissions are the intersection of server route ceiling, published skill ceiling, account policy, project restrictions, and requested operation. Project data can narrow but never expand authority.

### 2. E1 and E2 boundary

- E1 means retrieval-scoped candidates and deterministic projection/evaluation. It does not claim Hosted dispatch enforcement or filesystem isolation.
- E2 means context-bound execution: the parent process assembles the initial context, creates a signed run-bound envelope, and enforces it at the shared Hosted entrypoints. E2 does not claim that a child process cannot read other filesystem paths.
- E3 filesystem/process/network/secret isolation is outside this ADR and remains a separate Phase C decision and execution plan. ADR-0040 remains Proposed and is not an E3 implementation authority.

### 3. E2 Hosted Context Envelope

- The parent process creates a `jimuyun.hosted-context-manifest.v1` envelope outside the child write set.
- The envelope binds schema version, four dimensions, route/skill/operation, account/project/workspace/run/attempt/dispatch identity, policy/profile revisions, repository/template/project snapshots, allowed-read artifact manifest, allowed-write paths, output targets, context assembly result, budget profile, sandbox/network/tool policy, existing Hosted route contract evidence, execution/persisted prompt hashes, nonce, and time bounds.
- The envelope uses a canonical JSON payload and host-secret HMAC. Signature metadata and runtime validation state are excluded from the HMAC input and cannot be supplied by the child.
- Dispatch consumes a nonce atomically. A retry uses a new attempt, dispatch, nonce, and envelope. Expired, revoked, consumed, superseded, cross-account, cross-project, cross-run, or stale envelopes fail closed.
- The envelope aggregates existing Hosted route contracts. It does not redefine `hosted-route-recovery-order.v1`, `hosted-route-forbidden-source-scan.v1`, `project_route_prompt_evidence_bindings`, same-project succeeded-run binding, authoritative source-hash recomputation, `source_boundary_not_applicable`, or latest-live-blocker precedence.
- Gate mode is server-controlled per route and operation: `legacy`, `observe`, or `enforce`. Client and project input cannot select or raise the mode. E2 readiness is revoked when an enforced route rolls back to observe/legacy or when current evidence drifts.

### 4. Relationship to existing ADRs

This ADR **Extends ADR-0037**. ADR-0037 remains the authority that all Phase LLM/Codex calls use `ILlmRouteEngine`/`LlmRouteEngine`, `CodexHostedProcessCommandFactory`, or `scripts/sc/_llm_backend.py::run_llm_exec`. This ADR adds the Context Envelope and Scope Gate above those shared entrypoints; it does not redefine their invocation architecture.

This ADR **Complements ADR-0038**. ADR-0038 remains the authority for account-scoped readback, redaction, separate execution and persisted prompt hashes, database evidence binding, workspace-bound source evidence, and append-only failure evidence. This ADR aggregates those evidence products into a run-bound envelope; it does not create a competing prompt-security, readback, or evidence contract.

This ADR **does not supersede ADR-0037 or ADR-0038**. Any conflict is a fail-closed decision gap requiring an explicit ADR update or supersede decision before implementation.

### 5. Lifecycle and storage boundary

- Repository and template dynamic caches are host-owned and outside repository and Hosted workspace roots.
- Project projections are account/project/workspace-generation scoped and host-owned; a project-local pointer, if later required for compatibility, is a redacted derived pointer and never authority.
- Manifest, signature, nonce, revocation, gate, and readiness state are persisted in the Phase metadata authority or host-owned runtime state outside the child write set.
- Schema migrations are additive by default, preserve existing data, and require restart, recovery, rotation, revocation, and concurrent nonce tests.

### 6. Knowledge maintenance and consumption boundary

- Repository-fact maintenance pins the local committed `refs/heads/main` object ID at run start. It performs no implicit fetch, checkout, merge, or branch mutation, and dirty worktree bytes are not repository fact authority.
- An untargeted maintenance run is closed-world over source entries already registered in the current knowledge snapshot. A targeted run may discover only inside one explicit repository-relative consumer boundary; target-only worktree content remains provisional and cannot be promoted to repository fact.
- The repository-local maintenance Skill is a thin adapter over deterministic snapshot, catalog, projection, validation, and logging tools. It updates only derived knowledge artifacts, validated LKG pointers, and append-only evidence. It does not modify the inspected source or consumer object.
- Knowledge consumers use one deterministic Locator core. The first adapter is a versioned JSON stdin/stdout CLI; later CLI, Skill, Tool, MCP, or Phase adapters reuse the same core and contracts.
- Locator output is a source-location recommendation, not a synthesized fact answer. It includes module, repository-relative path, heading or symbol anchor, line range, source hash, ranking evidence, snapshot identity, confidence status, and an ordered read set that the caller rereads and hash-verifies.
- A caller LLM may provide semantic query intent and untrusted hints. A trusted adapter or server Registry owns permission scope, allowed Domains, authority commit, source snapshot, path policy, budget, and confidence policy. Only unresolved ambiguity may use the shared Python `run_llm_exec` path; no LLM output can widen the trusted envelope.

## Consequences

- E1 can be built and evaluated without claiming production Hosted enforcement.
- E2 implementation can reuse the existing shared entrypoints and evidence contracts instead of creating parallel route or prompt authorities.
- New schemas, fixtures, inventories, and validators are plan-local executable specifications before any Phase production-code change.
- Knowledge maintenance and consumption share deterministic cores and machine contracts instead of giving each caller its own retrieval or Git-comparison behavior.
- E3 isolation remains a separately authorized Phase C effort.

## Non-goals

- No OS-level filesystem, process, network, or secret isolation is decided here.
- No change is made to ADR-0037 or ADR-0038 by this ADR.
- No live metadata DB, live Hosted workspace, or production route is changed by accepting this ADR.

## References

- `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan.md`
- `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/00-index.md`
- `docs/adr/ADR-0033-phase-metadata-sqlite-local-disk.md`
- `docs/adr/ADR-0035-phase-controlled-runner-workspace-execution.md`
- `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`
- `docs/adr/ADR-0038-phase-evidence-sidecars-readback.md`
- `docs/adr/ADR-0040-phase-c-hardening-before-scaleout.md`
