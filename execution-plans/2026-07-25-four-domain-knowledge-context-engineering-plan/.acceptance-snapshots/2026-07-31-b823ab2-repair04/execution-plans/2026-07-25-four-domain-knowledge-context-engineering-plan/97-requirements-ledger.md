# Requirements Ledger

This Markdown is a human-readable projection of requirements-ledger.v1.json. The JSON ledger is the machine source for coverage.

| ID | Owner | Requirement | Acceptance ref | Status | Production policy |
| --- | --- | --- | --- | --- | --- |
| KC-001 | K1 | The standalone Markdown remains original-requirements input and the directory is the VDD plan authority after plan-ready. | `acceptance://KC-001/authority-chain` | active | forbidden |
| KC-002 | K1 | ADR-0044 is Accepted and explicitly extends ADR-0037, complements ADR-0038, and supersedes neither. | `acceptance://KC-002/adr-relationship` | active | forbidden |
| KC-003 | K1 | Every contract carries Domain, per-domain Visibility, Lifecycle Instance, and Enforcement Level. | `acceptance://KC-003/four-dimensions` | active | forbidden |
| KC-004 | K1 | The four domains and explicit dependency closure are versioned and fail closed on unknown values. | `acceptance://KC-004/domain-closure` | active | forbidden |
| KC-005 | K1 | Projection is derived_cache and never instruction authority. | `acceptance://KC-005/projection-authority` | active | forbidden |
| KC-006 | K1 | E1 is retrieval-scoped and cannot claim Hosted enforcement. | `acceptance://KC-006/e1-boundary` | active | forbidden |
| KC-007 | K1 | E2 is context-bound and E3 remains a separate Phase C scope. | `acceptance://KC-007/e2-e3-boundary` | active | forbidden |
| KC-008 | K1 | Server registries are the permission trust root and project data can only narrow permissions. | `acceptance://KC-008/permission-intersection` | active | forbidden |
| KC-009 | K1 | Repository, template, project and run lifecycles have independent cache identity. | `acceptance://KC-009/lifecycle-isolation` | active | forbidden |
| KC-010 | K0 | K0 uses only temporary synthetic roots, disposable DBs, fake accounts and canaries. | `acceptance://KC-010/synthetic-only` | active | forbidden |
| KC-011 | K0 | K0 never accesses live metadata, live workspace, real secret or real account content. | `acceptance://KC-011/no-live-path` | active | forbidden |
| KC-012 | K2 | All plan-local schemas have stable identities and closed root shapes. | `acceptance://KC-012/schema-inventory` | active | forbidden |
| KC-013 | K2 | Positive and negative fixtures exercise the same composition semantics. | `acceptance://KC-013/fixture-parity` | active | forbidden |
| KC-014 | K2 | Composition validation fails closed with targeted failure codes. | `acceptance://KC-014/fail-closed-order` | active | forbidden |
| KC-015 | K3 | The source snapshot is deterministic for the same eligible bytes and policy revisions. | `acceptance://KC-015/snapshot-replay` | active | forbidden |
| KC-016 | K3 | Windows path normalization rejects case collision, reparse escape and cache roots under protected roots. | `acceptance://KC-016/path-containment` | active | forbidden |
| KC-017 | K3 | Atomic build pointers, lock ownership and LKG recovery preserve failed evidence. | `acceptance://KC-017/lkg-recovery` | active | forbidden |
| KC-018 | K4 | Repository catalog excludes logs, live DB, workspace, raw prompt, dynamic cache and meta/knowledge. | `acceptance://KC-018/catalog-exclusion` | active | forbidden |
| KC-019 | K5 | Tokenizer and normalization revisions are fixed and include Chinese and code identifier rules. | `acceptance://KC-019/tokenizer-vectors` | active | forbidden |
| KC-020 | K5 | Ranking parameters, tie-breaks and score mapping are fixed before deterministic claims. | `acceptance://KC-020/ranking-vectors` | active | forbidden |
| KC-021 | K5 | K5 ambiguity classification delegates only through scripts/sc/_llm_backend.py::run_llm_exec. | `acceptance://KC-021/llm-delegation` | active | forbidden |
| KC-022 | K5 | Evaluation expands required and relevant source sets on a fixed snapshot with explicit glob semantics. | `acceptance://KC-022/evaluation-set` | active | forbidden |
| KC-023 | K6 | E1 Phase Projection is experimental, derived, provenance-bound and threshold-gated. | `acceptance://KC-023/e1-readiness` | active | forbidden |
| KC-024 | K7 | Template Projection derives managed paths from actual ProjectWorkspaceSeeder behavior. | `acceptance://KC-024/seeder-projection` | active | forbidden |
| KC-025 | K8 | Project Projection is isolated by account, project and workspace generation. | `acceptance://KC-025/project-isolation` | active | forbidden |
| KC-026 | K9 | Recovery Projection is redacted and excludes raw prompt, token, secret, host path and other account data. | `acceptance://KC-026/recovery-redaction` | active | forbidden |
| KC-027 | K10 | Context budgets are finite and required omissions block dispatch with evidence. | `acceptance://KC-027/budget-omission` | active | forbidden |
| KC-028 | K10 | The signed payload covers identity, policies, snapshots, read/write/output, assembly, budget, execution policy, hashes, nonce and time. | `acceptance://KC-028/signed-payload` | active | forbidden |
| KC-029 | K10 | The envelope aggregates existing recovery, prompt scan, DB binding, source hash, live blocker and explicit exemption contracts. | `acceptance://KC-029/contract-composition` | active | forbidden |
| KC-030 | K11 | Three caller inventories and a direct invocation inventory are generated from current source. | `acceptance://KC-030/inventory-generation` | active | blocked_until_gate |
| KC-031 | K11 | Inventory membership, reachability, status and source identity are not hand-counted or manually marked migrated. | `acceptance://KC-031/inventory-derived-status` | active | blocked_until_gate |
| KC-032 | K11 | K11-K13 production write is blocked until BH-HANDOFF or formal merge/supersede and explicit authorization. | `acceptance://KC-032/protected-gate` | active | blocked_until_gate |
| KC-033 | K12 | Gate mode is server-controlled; an E2 manifest is valid only in enforce, legacy or observe cannot declare E2, and rollback revokes E2 readiness. | `acceptance://KC-033/gate-mode` | active | blocked_until_gate |
| KC-034 | K12 | Migration keeps backward-compatible browser/API behavior and stable browser-safe error codes. | `acceptance://KC-034/compatibility-errors` | active | blocked_until_gate |
| KC-035 | K13 | E2 readiness is mechanically computed from current evidence and never hand-declared. | `acceptance://KC-035/e2-predicate` | active | blocked_until_gate |
| KC-036 | K14 | K14 maintains other projections, incremental rebuilds, bad cases, LKG and compatibility navigation. | `acceptance://KC-036/maintenance` | active | separate_authorization |
| KC-037 | K0 | No production code, live DB or live workspace is modified before plan-ready and later authorization. | `acceptance://KC-037/preimplementation-boundary` | active | forbidden |
| KC-038 | K0 | Original requirements and know1-know5 lineage hashes are preserved. | `acceptance://KC-038/source-lineage` | active | forbidden |
| KC-039 | K1 | ADR-0037 and ADR-0038 are not rewritten to carry the new Context Envelope decision. | `acceptance://KC-039/adr-nonreplacement` | active | forbidden |
| KC-040 | K13 | Bootstrap Review is gated on actual executable artifacts, deterministic preflight and explicit authorization. | `acceptance://KC-040/bootstrap-entry` | active | blocked_until_gate |
| KC-041 | K5 | The Knowledge Locator has one versioned request contract and one versioned location-result contract shared by every adapter. | `acceptance://KC-041/locator-request-result-schema` | active | forbidden |
| KC-042 | K5 | A caller LLM may provide semantic intent and hints, while an adapter or server Registry owns authority, permission, snapshot, Domain ceiling, path policy and budget fields; results bind the trusted path-policy identity. | `acceptance://KC-042/trusted-input-ownership` | active | forbidden |
| KC-043 | K5 | Locator v1 uses exact matching, scoped rg, tokenizer/BM25, relation expansion and deterministic tie-breaks without default LLM generation or embeddings. | `acceptance://KC-043/deterministic-locator-order` | active | forbidden |
| KC-044 | K5 | Locator output is a ranked source-location recommendation with path, anchor, line range, source hash, provenance and ranking evidence, never a generated fact answer. | `acceptance://KC-044/location-only-result` | active | forbidden |
| KC-045 | K5 | Matched retrieval permits only high or medium confidence; low-confidence retrieval returns insufficient_match with bounded candidates or an empty read set and does not infer a fact. | `acceptance://KC-045/insufficient-match` | active | forbidden |
| KC-046 | K5 | A caller passes an available consumer_ref instead of an LLM summary, and rereads each recommended source after verifying its snapshot and hash. | `acceptance://KC-046/consumer-ref-and-revalidation` | active | forbidden |
| KC-047 | K14 | K14 creates a repository-local maintain-knowledge-base Skill as a thin adapter over deterministic snapshot, catalog, projection, validation and logging tools. | `acceptance://KC-047/maintenance-skill-package` | active | separate_authorization |
| KC-048 | K14 | Without a target, maintenance is closed-world over registered source entries, starts from the requested knowledge snapshot, and cannot discover or add absent repository content. | `acceptance://KC-048/existing-only-closed-world` | active | separate_authorization |
| KC-049 | K14 | Targeted maintenance limits discovery to one explicit consumer boundary; only main-backed content becomes repository fact and target-only worktree content remains provisional. | `acceptance://KC-049/targeted-maintenance` | active | separate_authorization |
| KC-050 | K14 | Each maintenance run pins local refs/heads/main, performs no implicit fetch or branch mutation, and never treats dirty worktree bytes as repository fact authority. | `acceptance://KC-050/local-main-authority` | active | separate_authorization |
| KC-051 | K14 | Maintenance updates only derived knowledge artifacts, validated LKG pointers and append-only logs, and never modifies the inspected source or consumer object. | `acceptance://KC-051/maintenance-write-boundary` | active | separate_authorization |
| KC-052 | K5 | Only unresolved deterministic ambiguity may invoke the centralized K5 classifier through scripts/sc/_llm_backend.py::run_llm_exec, and its result cannot widen the trusted envelope. | `acceptance://KC-052/centralized-ambiguity-fallback` | active | forbidden |
