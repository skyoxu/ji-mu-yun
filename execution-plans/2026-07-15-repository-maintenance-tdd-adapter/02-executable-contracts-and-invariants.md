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
- backend, recovery, drift, P2, and release-authority policies.

The instance is a projection, not a second requirements document. Long prose remains in the owning books; the instance cites stable IDs and source references.

## Command Execution Contract

- `shell` is always `false`.
- Commands are stable registry entries, never raw command strings.
- Each command has a repository-resolved executable, structured `argv`, `cwd`, timeout, expected exit semantics, and expected failure IDs where applicable.
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

The baseline freezes HEAD, Git index tree, tracked diff, untracked manifest, authority hashes, plan/source/contract/schema/validator/test hashes, execution read set, dependency closure, and declared write set.

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
| `plan-ready` | `plan-ready` | slice, candidate, acceptance, handoff, release |
| `slice-ready` | `slice-ready` | candidate, acceptance, handoff, release |
| `implementation-candidate` | `bootstrap-review` | acceptance, handoff, release |
| `implementation-accepted` | `implementation-accepted` | handoff, release |

`implementation-accepted` requires current deterministic evidence, no open accepted P0/P1, and a disposition for every accepted P2. A high-risk P2 is non-deferrable. A deferral requires owner, non-impact proof, expiry or recheck trigger, and an exact closure test; expiry automatically blocks acceptance.

## S0 Slice Proof

`RMAP-S0` keeps `slice-ready` as its exit predicate. Its GREEN command is `rmap-s0-slice-validate`, which invokes the plan-local composite with `--predicate slice-ready --slice-id RMAP-S0`. The command checks the framework ADR, ownership standard, and both index projections; missing implementation outputs fail closed with `RMAP-AUTH-SLICE-EVIDENCE`. `plan-ready` is never accepted as a substitute.

The same command-to-exit rule applies to every slice. Each S0-S7 GREEN command has a unique command ID whose `declared_predicate` and `slice_id` exactly match the slice contract. The composite consumes `--slice-id`, verifies that binding, and checks the outputs or evidence owned by that slice. A generic test command or a command bound to another slice cannot authorize an exit.

The junction regression creates one uniquely named junction directly under `logs/`, points it at an existing outside directory, verifies resolved containment rejection, and removes it in `finally`. It does not depend on host `%TEMP%` or on creating a writable grandchild under a restricted token. Disposable test state never becomes plan authority.

S6 and S7 never discover evidence through a repository-wide `logs/**` scan. Their command contracts require explicit candidate-result and Bootstrap-run paths. The validator checks the candidate file's hash in the review manifest, current plan/source/slice identity, exact authority exclusions, review/preflight/disposition identity, required-check completion, and current finding disposition before authorizing a transition.

## Confidence Contract

Confidence is advisory. A score below 90 may trigger at most three internal improvement rounds, but cannot authorize any state. The machine predicate remains the only local authority.
