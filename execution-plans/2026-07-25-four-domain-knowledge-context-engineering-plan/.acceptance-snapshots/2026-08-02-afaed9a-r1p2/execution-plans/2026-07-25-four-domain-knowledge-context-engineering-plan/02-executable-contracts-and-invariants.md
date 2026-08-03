# Executable Contracts And Invariants

## Contract families

| Contract | Machine artifact | Observable decision |
| --- | --- | --- |
| Four dimensions | `schemas/knowledge-contract.v1.schema.json` | Every envelope and projection carries Domain, Visibility, Lifecycle and Enforcement |
| Source snapshot | `schemas/source-snapshot.v1.schema.json` | Same eligible bytes produce the same snapshot ID |
| Context envelope | `schemas/hosted-context-manifest.v1.schema.json` | A dispatch is bound to identity, policy, snapshots, read/write set, evidence, budget and nonce |
| Context signature | `schemas/context-envelope-reference-vector.v1.schema.json`, `fixtures/reference-vectors/jcs-hmac-reference-vector.v1.json` | JCS bytes, payload SHA-256 and HMAC-SHA-256 are recomputed from one synthetic envelope |
| Context assembly | `schemas/context-assembly.v1.schema.json` | Required omissions block dispatch and optional omissions are recorded |
| Caller inventory | `schemas/inventory.v1.schema.json` | Caller set is generated from current source, not hand-counted |
| Requirements | `schemas/requirements.v1.schema.json` | Every active requirement maps to one slice and one acceptance ref |
| Fixture case | `schemas/fixture-case.v1.schema.json` | Positive and negative cases exercise the same composition rules |
| Gate result | `schemas/scope-gate-result.v1.schema.json` | Server-owned gate mode and stable failure code are explicit |
| Locator request | `schemas/knowledge-locator-request.v1.schema.json` | Semantic intent is separated from adapter/Registry-owned authority, scope, snapshot and budget |
| Locator result | `schemas/knowledge-locator-result.v1.schema.json` | The output is an ordered source-location recommendation requiring source hash revalidation |
| Maintenance request | `schemas/knowledge-maintenance-request.v1.schema.json` | Existing-only and targeted modes pin local main and declare discovery/write boundaries |
| Maintenance result | `schemas/knowledge-maintenance-result.v1.schema.json` | Entry dispositions, provisional status, zero source mutation, LKG and append-only logging are observable |

## Hard invariants

1. Projection has `authority_class=derived_cache`, `instruction_authority=false`, and `may_override_source=false`.
2. Unknown Domain, Visibility, Lifecycle, Enforcement, policy revision, capability, gate mode or fixture failure code fails closed.
3. Effective permissions are an intersection of server route ceiling, published skill ceiling, account policy, project restrictions and requested operation.
4. Repository, template, project and run lifecycles do not share a cache namespace or LKG pointer.
5. Project-bound data has one account/project/workspace-generation identity; cross-account and cross-project sources are rejected.
6. K0-K10 never read or write live metadata, live Hosted workspaces, provider secrets, or real account content.
7. K5 ambiguity classification delegates only through `scripts/sc/_llm_backend.py::run_llm_exec`; no direct provider or `codex exec` construction is permitted.
8. The Context Envelope aggregates existing Hosted route contracts rather than defining a competing recovery or prompt-security contract.
9. Manifest HMAC covers the canonical payload, including parsed permission inputs and contract evidence; signature metadata and runtime validation state are excluded.
10. Nonces are atomically consumed; a retry creates a new attempt, dispatch and nonce.
11. Required context omissions make `assembly_status=blocked` and prevent a model call.
12. Inventory migration status is derived from source and evidence, never manually assigned.
13. `enforcement_level=E2` requires `gate_mode=enforce`; `legacy` and `observe` cannot carry an E2 declaration, and rollback from `enforce` revokes E2 readiness.
14. E3 is never inferred from E1, E2, a projection, or Bootstrap output.
15. All adapters use one Locator core; v1 retrieval order is exact match, scoped `rg`, tokenizer/BM25, relation graph, then deterministic tie-break.
16. Locator output is `location-recommendation`, never a generated fact answer; every returned source requires snapshot/hash revalidation.
17. Caller LLM input is limited to semantic intent and untrusted hints. Trusted envelope ownership is `adapter` or `server-registry` only; its path-policy identity and repository-relative prefix boundaries are mandatory and result-bound.
18. `matched` permits only `high` or `medium` confidence. `insufficient_match` carries lower-confidence outcomes, returns bounded candidates or an empty read set, and never upgrades uncertainty into a fact.
19. Maintenance pins the local committed `refs/heads/main` object ID, performs no implicit fetch, and does not treat dirty worktree bytes as repository fact authority.
20. Untargeted maintenance is closed-world over registered source entries and its result `before_snapshot_id` equals the request `knowledge_snapshot_id`; targeted discovery is contained to one explicit consumer boundary.
21. Target-only worktree content remains provisional and cannot be promoted to a main-backed repository fact.
22. Maintenance writes only derived knowledge artifacts, validated LKG pointers, and append-only logs; inspected source and consumer objects remain unchanged.

## Existing contract composition

The validator must resolve and check these existing products when a route is applicable:

- `hosted-route-recovery-order.v1`
- `hosted-route-forbidden-source-scan.v1`
- `project_route_prompt_evidence_bindings`
- same-project succeeded run binding
- authoritative source-hash recomputation
- latest live platform acceptance blocker precedence
- explicit `source_boundary_not_applicable`

The plan-local envelope stores references and hashes to these products; it does not duplicate their semantics.
