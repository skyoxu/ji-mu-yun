---
document_type: source-brief
status: proposed
scope: repository-toolchain-control-plane-only
source_id: TC-D1-REBUILD
repository_ref_reviewed: 0dce7806c93e5e0ca4ac4faed61baa13735c8983
updated_date: 2026-09-11
supersedes_scope: docs/know.md TC-D1 sections only
---

# TC-D1 Skill Replay Portability And Evaluation Seed Rebuild Source Brief

## 1. Purpose

This is the new upstream input for repairing the existing
`execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/`
directory. It should proceed through `bmad-prd`, `bmad-spec`, and
`bmad-architecture` before that directory is repaired.

This brief does not authorize a second TC-D1 directory, implementation,
lifecycle publication, reuse of the `tool` branch's Acceptance, or a completion
claim for `0dce7806`. Existing 08-01 and 08-05 history remains append-only.

## 2. Current Reality

The repository already has ADR-0058, a repository-owned replay CLI and bounded
capability descriptor, historical compatibility and evaluation-seed artifacts,
consumer integration, and round-6 real subprocess evidence. Skill-input v2 now
supersedes v1 for live gates under ADR-0060.

These assets reduce new construction but do not close independent-review gaps:

- the requested target is not proven to be the target every adapter inspects;
- validator and semantic-dependency identities are incompletely bound;
- six matrix labels do not prove six independent scenarios or a real
  stable-versus-candidate comparison;
- downstream terminal and rollback behavior are incompletely demonstrated;
- original requirements lack exact cover by assertions and evidence;
- round-6 Q8 is non-authorizing and is not a fresh `acceptance-passed` result.

## 3. Outcome

Repair TC-D1 so a reviewer can reconstruct from current bytes and real process
evidence which package was requested, which validator and dependencies inspected
it, how stable and candidate behaved on independent scenarios, how invalid input
failed, how consumers behaved, and how disable/rollback restored the prior route.
Labels, prefilled observations, JSON equality, and historical Acceptance are
insufficient completion evidence.

## 4. Scope

In scope are the existing TC-D1 directory and append-only repair rounds,
repository replay code under `scripts/sc/**`, current Toolchain consumers,
detached fixtures and tests, Toolchain evidence under `logs/**`, and a current
Skill-input v2 Acceptance handoff after independent review.

Out of scope are TC-E0 and TC-D2-D6 implementation; Phase service, runtime,
browser/API, accounts, hosted workspaces and user sandboxes; rewriting history;
baseline promotion, Miner/Memory, autonomous Skill changes, learned ranking or
RL; and creation of a replacement TC-D1 directory.

## 5. Requirements

### D1-R1 Historical preservation and authority

Preserve tracked 08-01 and prior 08-05 bytes and lifecycle evidence. New work
uses an append-only repair round with a current Git baseline and Skill-input v2
binding. Historical Acceptance grants no current authority. Any bound-source
change makes the current result stale.

### D1-R2 Requested target is the inspected target

Reject a missing, non-directory, escaping, or unsupported target. Every adapter
must receive or derive that exact target through a declared interface. Evidence
must bind requested identity to files actually read; hashing one directory next
to an unrelated successful command is not proof.

### D1-R3 Validator and dependency identity

Resolve capability through an explicit root and entrypoint. Verify trusted
content identity for the validator and dependencies that affect semantics.
Missing, substituted, drifted, incompatible, escaping, or always-success
validators fail before a success receipt. Self-reported version text is not
trusted identity.

### D1-R4 Real positive and negative probes

Materialize independent valid and invalid detached packages and run the selected
validator against each. The valid package passes; the invalid package fails for
the intended reason. Evidence binds command, target, exit code, output hashes,
and process receipt. Prefilled probe rows are forbidden.

### D1-R5 Historical compatibility

Preserve the machine-bound historical command and verify native references and
hashes. Execute the current wrapper on a current detached equivalent and record
the limits of equivalence. This observation cannot claim the old command was
portable or turn replay into new historical authority.

### D1-R6 Evaluation-seed provenance

Retain `candidate-baseline-contamination`,
`self-hosted-knowledge-read-set-collision`, and
`toolchain-policy-architecture-index-gap` as non-authorizing candidates. Each
binds native evidence, hashes, provenance, applicability, missing labels, and a
counterexample or its explicit absence. TC-D1 cannot promote evaluation sets or
a quality baseline.

### D1-R7 Real stable-versus-candidate matrix

Use two immutable, independently identifiable implementations or packages.
Every case names its fixture, validation surface, stable command, candidate
command, expected observation, and comparison rule. Execute both sides and keep
separate process evidence.

The minimum six materially distinct cases are: valid package, invalid package,
historical compatibility, dirty baseline, knowledge read-set collision, and
closed-policy architecture-index gap. Each uses a distinct fixture or state
transition. The matrix fails on skipped or duplicate cases, wrong targets,
unlaunched commands, reused evidence, or copied expected values.

### D1-R8 Downstream consumers

Run every declared current Toolchain consumer through its actual package
interface and rerun the workflow-model-routing terminal consumer as one
compatibility observation. Terminal validation rejects a missing consumer,
wrong target, stale receipt, unexecuted command, and route checks reachable only
inside a failure branch.

### D1-R9 Disable and rollback

Define old and new routes as observable states. Exercise enable, disable,
rollback, and re-enable in isolation. After disable/rollback, a caller must run
the prior route and reproduce prior behavior. A flag or configuration value is
insufficient. Preserve failed candidate and historical evidence.

### D1-R10 Exact cover and final evidence

Provide bidirectional exact cover from every requirement to acceptance
assertions, selectors, commands, and runtime evidence, and back to its source.
Each behavioral assertion has an independently observable failure. The final
snapshot is reproducible from roots covering code, fixtures, plans, consumers,
and tests that determine the result.

### D1-R11 Authority separation

Replay, seed, matrix, review, and Quick Dev outputs use `authorizes: []`. Quick
Dev establishes only its implementation predicate. Independent review precedes
fresh deterministic Acceptance, which alone owns a new `acceptance-passed` and
must consume current Skill-input v2.

## 6. Required Defect-Revealing Tests

Before production changes, tests must fail when:

- the target is absent or the validator inspects another target;
- a validator always succeeds, drifts, is substituted, or accepts an invalid
  package;
- a matrix case is skipped, reuses evidence, or reports pass without execution;
- stable and candidate incorrectly resolve to the same identity;
- downstream routing is skipped on the success path;
- rollback changes configuration without restoring caller behavior;
- a snapshot cannot be reconstructed or becomes stale;
- a derived receipt claims foreign lifecycle authority.

Tests assert observable behavior, exit status, read/target identity, and evidence
linkage. Schema shape and JSON equality may support but cannot solely prove them.

## 7. PRD, Spec, And Architecture Handoff

`bmad-prd` should define outcomes and success without inheriting the old four
slices. `bmad-spec` should produce atomic obligations and bidirectional exact
cover. Architecture must decide adapter semantics, dependency identity,
stable/candidate isolation, snapshot reconstruction, rollback state, and
evidence ownership before VDD repair.

Those documents must classify every old TC-D1 requirement as retained,
superseded, narrowed, or removed. Round-6 Q8 and old Acceptance are inputs, not
proof of the rebuilt requirements.

## 8. Evolution Decisions

Retained and strengthened: portable execution, historical preservation, bounded
capabilities, real probes, cautious seeds, stable/candidate comparison,
downstream replay, rollback, and non-authorizing evidence.

Covered by later evolution and removed as new work: live Skill-input protocol
design (owned by ADR-0060/v2), creation of TC-D1, and initial creation of the
replay CLI, descriptor, ADR, seed schema, and historical manifest where current
artifacts can be repaired.

Discarded: completion from labels, receipt presence, copied values, or repeated
unverified JSON; one consumer as universal quality proof; self-reported version
as identity; configuration-only rollback proof; autonomous promotion, general
SkillOS, percentage canaries, and a presumed RL endpoint.

## 9. Next-Stage Sources

Bind current bytes of repository `AGENTS.md`, the Toolchain workflow index, this
brief, TC-D1 contracts and repair evidence, `docs/fix80501.txt` as non-authority
external review input, ADR-0058 and ADR-0060, current planning/TDD/review/
Acceptance Skills, replay code and tests, historical 08-01 evidence, and the
declared downstream consumer. Report conflicts with current ADRs or Skill
contracts explicitly.
