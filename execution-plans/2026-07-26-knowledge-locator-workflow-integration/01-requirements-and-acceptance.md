# Requirements And Acceptance

This file is the compact owner for user intent, requirement coverage, acceptance, and source lineage. The user explicitly requested a complete VDD directory for a deterministic Knowledge Locator CLI plus VDD preflight, Quick Dev, and Bootstrap prepare adapters.

| ID | Slice | Requirement | Observable acceptance | Source |
| --- | --- | --- | --- | --- |
| KWI-001 | RMAP-S0 | Add an Accepted ADR for repository knowledge consumption without reopening the completed 2026-07-25 plan. | ADR-0048 is Accepted, indexed, extends ADR-0044, complements ADR-0037/0041/0043, and supersedes none. | ADR-0044; user-approved design |
| KWI-002 | RMAP-S0 | Repository source remains fact authority and all indexes remain `derived_cache`. | Authority tests reject answer authority, dirty-worktree fact promotion, and implicit fetch. | ADR-0044 section 1 and 6 |
| KWI-003 | RMAP-S1 | Promote Locator request/result, context-selection, and minimal consumption-decision contracts from the dated plan to a stable repository-owned `knowledge/contracts/` root. | Stable contracts validate; consumption decisions remain adapter-owned; dated v1 bytes remain readable migration inputs and are no longer a runtime dependency. | KC-041; KC-046 |
| KWI-004 | RMAP-S1 | Add a versioned consumer-policy registry owned by trusted adapters. | Registry owns domain/path/budget/confidence limits for VDD, Quick Dev, and Bootstrap; LLM-owned envelopes fail. | KC-042 |
| KWI-005 | RMAP-S2 | Implement one JSON stdin/stdout Locator CLI, reusable deterministic core, and index builder with validated staging, single-owner-or-verified-reuse concurrency, atomic pointer replacement, and failed-build LKG preservation. | Repeated identical request/snapshot bytes produce byte-identical location results; concurrent, unvalidated, non-atomic, and failed-build fixture vectors preserve one validated immutable generation and the previous LKG. | ADR-0044 section 6; KC-017 |
| KWI-006 | RMAP-S2 | Fix retrieval order to exact path/identifier/symbol, scoped `rg`, tokenizer/BM25, relation expansion, then stable tie-break. | Chinese, code identifier, path, symbol, tie-break, and budget vectors pass. | KC-043 |
| KWI-007 | RMAP-S2 | Locator output is location-only and requires reread/hash verification. | Result contains path, anchor, line range, source hash, provenance, rank evidence and no generated answer field. | KC-044; KC-046 |
| KWI-008 | RMAP-S2 | Low confidence, stale catalog, policy drift, out-of-policy paths, or source hash drift fail closed. | Exact negative cases return `insufficient_match` or a stable blocked process code without a matched fact. | KC-045 |
| KWI-009 | RMAP-S2 | LLM retrieval is disabled by default; explicit ambiguity fallback delegates only through `run_llm_exec`. | Direct provider/Codex use is absent and fallback cannot widen the trusted envelope. | KC-052; ADR-0037 |
| KWI-010 | RMAP-S3 | VDD runs knowledge preflight after mandatory authority reads and before freezing plan sources. | Adapter writes a hash-bound knowledge context while keeping `AGENTS.md`, lifecycle, and user sources mandatory. | VDD Skill; ADR-0043 |
| KWI-011 | RMAP-S3 | VDD policy distinguishes required from optional knowledge modules. | Missing required modules block `plan-ready`; optional `insufficient_match` remains explicit and non-authorizing. | VDD completion contract |
| KWI-012 | RMAP-S4 | Quick Dev consumes only the VDD-frozen context and does not issue a new semantic query. | `verify-bound` reproduces the result; any expansion or changed source routes to VDD repair before RED. | Quick Dev freshness contract |
| KWI-013 | RMAP-S4 | Slice Capsules bind the exact knowledge subset, snapshot, policy, and hashes. | Capsule/evidence tests reject undeclared knowledge, execution-read-set escape, and predecessor drift. | Quick Dev backend contract |
| KWI-014 | RMAP-S5 | Bootstrap may locate context once before prepare and then freezes it in the review input and Artifact View. | Prepare records request/result/context hashes; post-prepare context growth invalidates launch and gate. | ADR-0041; Bootstrap standard |
| KWI-015 | RMAP-S5 | Locator may satisfy or augment mapped context classes but cannot weaken profile completeness. | Every required context class remains nonempty and reviewers read exactly the frozen manifest. | Bootstrap profile contract |
| KWI-016 | RMAP-S5 | Reviewer/verifier children never invoke Locator or read live recommended sources. | Runtime prompts and tests enforce frozen snapshot-only reads. | Bootstrap Artifact View contract |
| KWI-017 | RMAP-S6 | Maintenance and consumption share stable catalogs without hidden writes. | Stale main/catalog returns `knowledge_refresh_required`; explicit maintenance refreshes derived data and append-only logs. | maintain-knowledge-base; KC-047..KC-051 |
| KWI-018 | RMAP-S6 | Existing plans and finalized review evidence remain byte-preserving compatibility inputs. | Migration cases cover dated contracts, plans without knowledge context, and historical Bootstrap runs without rewriting them. | VDD freshness; ADR-0041 |
| KWI-019 | RMAP-S6 | Rollout uses shadow comparison before enforce and preserves a deterministic bypass-free enforced mode. | Shadow evidence compares recommended versus required reads; enforce has no caller-controlled policy bypass. | ADR-0044 trusted envelope |
| KWI-020 | RMAP-S7 | One terminal validator covers Locator, all adapters, consumption decisions, migration, Skill contracts, and forbidden-path scanning. | Terminal command exits zero only when all declared suites pass, rejected candidates never satisfy required coverage, and no live Phase path was accessed or modified. | VDD self-hosted profile |
| KWI-021 | RMAP-S3 | VDD records one adapter-owned consumption decision for every Locator candidate after reread without modifying Locator result bytes. | Frozen context binds each candidate reference and hash to `accepted` or `rejected`, a bounded rejection reason, and satisfied modules; rejected candidates do not satisfy required modules and an all-rejected required module blocks `plan-ready`. | User-approved semantic-fit refinement |
| KWI-022 | RMAP-S4 | Quick Dev verifies the exact VDD-frozen consumption decisions and cannot issue, add, or reclassify them. | Verify-bound and Slice Capsule tests route any decision reclassification, candidate addition, or satisfied-module expansion to VDD repair before RED. | User-approved semantic-fit refinement |
| KWI-023 | RMAP-S5 | Bootstrap prepare records its own adapter-owned consumption decisions before freezing Artifact View. | Only accepted candidates with nonempty satisfied context classes count toward profile completeness; rejected candidates remain reason-bound metadata, and reviewer/verifier children cannot change a decision. | User-approved semantic-fit refinement |

## Consumption Decision Boundary

Locator results remain immutable and location-only. After rereading a candidate and verifying its source hash, the trusted consumer adapter records exactly one decision containing the candidate reference, `accepted` or `rejected`, a bounded rejection reason when rejected, and the required module or context class satisfied when accepted. Accepted decisions require a nonempty `satisfies` set; rejected decisions have an empty `satisfies` set and never count toward completeness.

The initial rejection reasons are `wrong_domain`, `insufficient_specificity`, `authority_conflict`, and `duplicate`. The decision is embedded in the consumer's existing frozen context rather than creating an independent runtime authority artifact.

## Clarifications

No unresolved material clarification remains. The stable root is `knowledge/`; the canonical first adapter is a repository Python CLI; adapters own trusted envelopes and semantic-fit consumption decisions; Locator output remains location-only; Quick Dev is verify-bound; Bootstrap locates only before prepare; no Phase production route is in scope.

## Acceptance Boundary

Targeted tests prove individual slices but authorize no lifecycle state. Only the registered terminal integration command may support `implementation-complete`. Acceptance, deployment, handoff, release, and archive remain external.
