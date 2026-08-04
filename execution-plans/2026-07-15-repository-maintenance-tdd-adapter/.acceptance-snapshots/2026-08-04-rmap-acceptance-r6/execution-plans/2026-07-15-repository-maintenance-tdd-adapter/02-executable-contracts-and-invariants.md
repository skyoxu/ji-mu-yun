# Executable Contracts And Invariants

## Ownership Invariant

The runtime common schema has exactly one eventual owner: the repository adapter Skill. This plan carries the pre-implementation schema candidate required to prove implementability. P0 moves that candidate into the Skill and changes plan instances to reference the Skill-owned revision without leaving two live schema authorities.

## Implementation Contract

Every contract instance binds:

- plan ID and source revision;
- exact requirement and acceptance IDs;
- authority source paths and hashes;
- slice dependencies;
- allowed production, test, and documentation write sets;
- forbidden paths;
- execution read set and dependency closure;
- stable command IDs;
- RED expected failure family and stable failure IDs;
- GREEN and REFACTOR proof commands;
- review profile and exit predicate;
- backend, recovery, drift, runtime P2 disposition, re-entry, and release-authority policies.

[`schemas/acceptance-contracts.v1.json`](schemas/acceptance-contracts.v1.json) owns the executable requirement -> acceptance -> slice -> command -> negative fixture -> evidence chain. [`schemas/authority-manifest.v1.json`](schemas/authority-manifest.v1.json) owns the complete clean-checkout authority closure.

The instance is a projection, not a second requirements document. Long prose remains in the owning books; the instance cites stable IDs and source references.

## Target Plan Lifecycle Contract

`RMAP-028` and `RMAP-029`, their acceptance entries, and their S1/S2 mappings define the target-plan lifecycle and non-authoritative report index behavior without extending the closed public implementation-contract schema.

Before the first implementation write or identity freeze, Quick Dev reads `execution-plans/95-implementation-report-index.v1.json`, validates an exact contained hit, and on a miss inspects only the current target execution-plan directory. It never recursively scans other plan directories. If it creates the canonical report, the report and sorted unique index entry are one pre-implementation change. It then locates the registered composite validator, requires exactly one `95-*.md`, and audits the complete plan authority and implementation readiness. A stale, escaping, duplicate, or ambiguous index/report, a missing validator, or an unresolved material defect fails closed.

When the audit finds a material defect, Quick Dev enters `vdd-execution-plan` repair mode and obeys its clarification and write gates. It repairs every affected plan artifact, runs the target's registered plan validator to PASS, appends the audit and change record to the target report, then refreezes source, authority, contract, validator, command, baseline, and candidate identities before RED. No pre-repair identity or evidence may be reused. A clean audit still requires durable audit evidence, but it does not manufacture a change entry.

The target report is append-only and excluded from both authority and candidate hashes. Its change entry records the defect, affected contracts, modified files, validation command/result, evidence, and remaining gaps. Its overall implementation entry is permitted only when the target contract identifies a terminal slice or predicate and the current registered terminal result passes. That entry records commands, exit codes, test counts, hashes, changed files, evidence, and residual gaps. Non-terminal slice results, assistant summaries, report prose, and successful process exit alone cannot trigger or authorize the entry.

## Persisted Slice Context Capsule

Each backend invocation consumes one immutable `context/<capsule-id>/` revision containing `context-manifest.v1.json` and `slice-capsule.v1.json`. Every artifact reference declares exactly one `path_type` (`repo_path`, `plan_path`, or `run_path`), safe relative path, role where applicable, and actual byte SHA-256. The context manifest is the deduplicated exact union of every Capsule artifact reference; omitted, extra, duplicate, ambiguous-root, stale-byte, or raw blocker payload references fail closed. The Capsule contains references, stable IDs, boundaries, predicates, and hashes only; it cannot rewrite requirements or carry mutable stage state. Later revisions bind `predecessor_capsule_hash` and never overwrite earlier bytes.

The context manifest binds the Capsule hash plus all referenced artifacts. The Capsule has `authorizes=[]`; S2 Capsules expose only `slice-ready`, while S6 may project `implementation-candidate` without authorizing that transition itself. A deterministic registered predicate result remains the only transition authority.

## Agent Attempt Ledger

Each `attempts/<attempt-id>/` directory contains a minimized backend request envelope, untrusted backend response envelope, adapter-generated canonical diff manifest, and adapter decision written last. Raw request or response bodies, secrets, personal data, and authoritative actor identity claims are forbidden. Raw content is represented only by approved hashes.

Attempts use monotonic IDs, request and decision predecessor links, and a previous decision hash. Accepted stages form only a legal `RED -> GREEN -> REFACTOR` prefix; S2 and S6 exit require all three exactly once. Each attempt has an exact event lifecycle, and every event artifact reference is checked against actual bytes. The adapter recomputes response/diff file equality, command allowlist membership, Capsule-boundary scope, baseline snapshot bytes, per-attempt result snapshot bytes, and the canonical diff hash. The decision binds a stable stage ID and expected stage-result path; the stage result binds the finalized decision hash without a content-hash cycle.

`attempt-ledger-manifest.v1.json` closes every request, response, diff, decision, and stage-result hash plus the raw `run-events.jsonl` byte hash and final canonical event hash. Missing decision, partial write, stale hash, forbidden/unrelated accepted diff, incomplete lifecycle, multiple accepted lineages, stale ledger root, or authority escalation fails closed. `adapter-decision` may record `accepted_for_validation`; it never authorizes a state change, and S6 alone may bind the final accepted attempt and ledger closure into the candidate envelope.

## Standard Stage Evidence Projection

`stage-evidence-projection.v1.schema.json` is the non-protocol lineage input for S0, S1, S3, S4, and S5. It binds immutable RED, GREEN, and REFACTOR result bytes, a frozen baseline file set, and the slice-local effect fold. It is not an attempt ledger, cannot claim acceptance authority, and may not be used for S2 or S6. Candidate lineage independently verifies its stage-result hashes, effect continuity, root hash, and predecessor chain.

## Command Execution Contract

- `shell` is always `false`.
- Commands are stable registry entries, never raw command strings.
- Each command uses the allowlisted `py` executable with structured `argv`, `cwd`, and timeout. RED/GREEN/REFACTOR expected exits, selectors, and failure IDs belong to the slice invocation contract, not the reusable command descriptor.
- Environment keys come from an explicit allowlist. Secret-bearing values are never stored in the contract or evidence.
- Substitution uses typed placeholder objects. Free-form `${...}` interpolation is invalid.
- Windows paths are resolved, normalized case-insensitively, checked for repository containment, and rejected when a reparse-point escape cannot be disproved.

## Backend Contract

Backend v1 is an in-session Slice Capsule executor with:

- no hidden mutable state;
- no provider scheduling;
- no subprocess ownership;
- no semantic review authority;
- no `done`, commit, acceptance, handoff, or release authority;
- permission only to produce changes within the current write set and report attempted commands, blockers, and candidate status.

The adapter independently recomputes the diff, hashes, command evidence, and acceptance state. A backend self-report is never proof.

## RED, GREEN, And REFACTOR State Machine

`initialized -> prepared -> red-observed -> green-observed -> refactor-verified -> implementation-candidate -> bootstrap-reviewed -> implementation-accepted`

Terminal or side states are `blocked`, `failed`, `stale`, and `superseded`.

- RED permits changes only to declared tests, fixtures, and current run evidence. Production changes before RED produce `implementation_before_red`.
- RED passes only when the expected assertion/failure ID is observed. Immediate pass, compile error, harness failure, and unrelated regression are distinct failures.
- GREEN opens only the declared production write set and requires current RED evidence.
- REFACTOR opens only declared cleanup/documentation paths and preserves GREEN.
- Drift marks the original run `stale`; its successor starts at `initialized`, references the predecessor, and never starts as stale.

## Baseline And Drift Contract

The baseline freezes HEAD, Git index tree, scoped tracked diff, scoped untracked manifest, authority hashes, plan/source/contract/schema/validator/test hashes, execution read set, dependency closure, and declared write set. Worktree manifests cover the declared slice closure through S6; unrelated unstaged and untracked paths are excluded, while whole-index drift remains blocking.

Every entry in `implementation-contract.v1.json.authority.source_hashes` is a concrete `sha256:<64 lowercase hex>` value. `runtime-bound` and other symbolic values are invalid. Prepare and resume recompute each referenced book and fail with `RMAP-HASH-AUTHORITY` before consuming older RED or candidate evidence.

Block on:

- any Git index drift;
- authority, contract, schema, validator, command-registry, execution-read-set, or dependency-closure drift;
- pre-existing or concurrent write-set overlap;
- a newer live acceptance blocker.

Unrelated worktree drift outside all bound sets is recorded but does not block.

## Predicate Authority

| Predicate | Authorizes | Explicitly does not authorize |
| --- | --- | --- |
| `plan-repair-verified` | `plan-repair-verified` | plan-ready, slice, candidate, acceptance, handoff, release |
| `plan-ready` | `plan-ready` | slice, candidate, acceptance, handoff, release |
| `slice-ready` | `slice-ready` | candidate, acceptance, handoff, release |
| `implementation-candidate` | `bootstrap-review` | acceptance, handoff, release |
| `implementation-accepted` | `implementation-accepted` | handoff, release |

`implementation-accepted` requires current deterministic evidence, no open accepted P0/P1, and a disposition for every accepted P2. A high-risk P2 is non-deferrable. A deferral consumes the repository Bootstrap schema and requires owner authority chained to the profile-bound root, non-impact evidence, a root-authorized executable/argv/cwd/runner descriptor, current recheck evidence, expiry, and a trigger. Process success is independently derived from the append-only runner event, descriptor hash, exit code, and stdout/stderr bytes; a handwritten result is invalid. Successful closure-process evidence is required when the disposition becomes fixed or refuted. The finalized envelope directly binds verifier and applicable P2 bytes; file existence or a metrics-only link is insufficient.

The current [`review-blocking-state.v1.json`](schemas/review-blocking-state.v1.json) blocks all predicates above `plan-repair-verified`. A local pass cannot clear or rewrite that disposition.

## S0 Slice Proof

`RMAP-S0` keeps `slice-ready` as its exit predicate. Its GREEN command is the non-authorizing `rmap-s0-preflight`, which proves only the current `plan-ready` baseline. After RED, GREEN, and REFACTOR evidence is recorded, `rmap-s0-slice-validate` invokes the plan-local composite with `--predicate slice-ready --slice-id RMAP-S0` as the final exit gate. The final gate checks the existing Accepted ADR-0041, the new ownership standard, both index projections, and the absence of a colliding ADR-0041 path; missing implementation outputs fail closed with `RMAP-AUTH-SLICE-EVIDENCE`. `plan-ready` is never accepted as a substitute for `slice-ready`.

The final post-REFACTOR command-to-exit rule applies to every slice. Each S0-S7 final command has a unique command ID whose `declared_predicate` and `slice_id` exactly match the slice contract. S0 and S1 use non-authorizing plan-ready preflights for GREEN and REFACTOR, because their final `slice-ready` commands consume the stage evidence written only after those stages. A GREEN or REFACTOR preflight cannot authorize an exit. The composite consumes `--slice-id`, verifies that binding, and checks the outputs or evidence owned by that slice. A generic test command or a command bound to another slice cannot authorize an exit.

The junction regression creates one uniquely named junction directly under `logs/`, points it at an existing outside directory, verifies resolved containment rejection, and removes it in `finally`. It does not depend on host `%TEMP%` or on creating a writable grandchild under a restricted token. Disposable test state never becomes plan authority.

Every slice command receives an explicit run directory plus RED, GREEN, and REFACTOR result paths. Stage results bind the current contract and validator hashes, one nonempty run ID, increasing observation timestamps, a predecessor-file hash chain, the declared command/selector/failure IDs, and observed exit codes. `recovery-state.json` binds the same run and current hashes. S2 and S6 also require a valid persisted Capsule and attempt event chain. Each S0-S6 exit may cache a schema-valid immutable `candidate-slice-effect.v1.json`, but the cache is never a fact source. The global baseline records only scoped files that actually exist at the initial boundary. A path absent from that baseline may first appear only as an accepted add with `before_sha256=null`; its first slice/run and after hash then become part of the derived state and every later slice must continue that hash. The validator loads each complete protocol run, validates ledger/stage/event/diff facts, derives accepted attempts from adapter decisions, folds real diff manifests, and recomputes the final event before comparing the cache. S6 does not consume Bootstrap output; its candidate binds a versioned cumulative `changed-files.json`, `candidate-lineage-manifest.json`, reproducible binary-safe `test-diff.patch`, final context-manifest and Capsule hashes, stage run IDs, accepted attempt-ledger manifest hash, raw event-log hash, final canonical event hash, accepted attempt fold, accepted attempt ID, and accepted decision hash. Cross-slice lineage uses `previous_slice_id`, `previous_slice_run_id`, and `previous_slice_effect_hash`; same-slice retry/supersession keeps `predecessor_run_id` and `supersedes_run_id`. The validator independently requires exact equality among the scoped tracked-plus-untracked Git diff, derived cumulative fold, and candidate manifest. Rename inference is disabled and represented as delete plus add.

S7 has its own run ID and consumes a separate `candidate-result-ref.json` containing the exact S6 run ID, repository-relative path, byte hash, semantic candidate hash, predicate, and a hash-bound `candidate-supersession-proof`. The proof consumes current recovery state, append-only events, and final event hash; the validator independently scans the canonical S6 recovery root for successor references. A Boolean or caller-supplied empty successor assertion is invalid. S7 then consumes the repository Skill's v2 finalized-run validation envelope and reruns the Bootstrap producer against the current run. It verifies matching candidate bytes, complete profile/control-plane/policy/validator identity, direct hashes for every final artifact including verifier and applicable P2 dispositions, non-authorizing boundaries, and finding closure.

The immutable Round 3 blocker is never edited to authorize re-entry. `review-policy-reentry.v1.json` binds its byte hash and may select a successor only through the repository-owned `bootstrap-successor-policy-decision.v1` schema and a hash-bound authorization event. Its authority source must chain to the exact root registry frozen by the successor policy revision; a run-local null-predecessor source is invalid. The consumer reruns the Bootstrap finalized validator and derives independence from distinct change, review, policy, authority, and input lineage; no `independent` Boolean exists. Pending states authorize nothing.

The Codex Home binder at `C:/Users/Administrator/.codex/skills/run-phase-bootstrap-review/scripts/verify_artifact_proof_boundary.py` is a provisional diagnostic verifier, not ordinary plan authority. The repository root, guard, and VDD Skill mirror remain workflow-integrity controls. Their inability to resist malicious Administrator control does not block `plan-ready`; it remains relevant only to `protected-handoff` and `release-ready`. Repository-only root/guard drift still fails with `RMAP-ARTIFACT-PROOF-PROTECTED-ROOT`, and every proof and diagnostic envelope has `authorizes=[]`.

Every formal proof records all seven dimension verdicts. A verdict is exactly `PASS`, with one registered executable rule, or `N/A`, with a machine reason code and reason allowed by the artifact-type contract. Static contracts and authorization-participating runtime artifacts require seven `PASS` verdicts. A non-authorizing derived view may use only type-authorized `N/A`; implementation convenience is never a valid reason. Static schemas prove a zero runtime authorization boundary with `authorizes=[]` and explicit high-level exclusions.

## Confidence Contract

Confidence is advisory. A score below 90 may trigger at most three internal improvement rounds, but cannot authorize any state. The machine predicate remains the only local authority.
