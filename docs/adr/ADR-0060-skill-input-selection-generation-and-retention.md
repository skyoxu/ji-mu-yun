# ADR-0060: Skill-Input Typed Selection, Immutable Generations, And Retention

- Status: Accepted
- Date: 2026-08-18

## Context

The v1 Skill-input protocol conflates source selection with source content and
uses filename-oriented exclusions to avoid generated artifacts. That permits
self-referential evidence graphs, makes receipt discovery depend on directory
ordering, and cannot describe adapter-owned page coverage or retention safely.

## Decision

- Skill-input v1 remains a historical compatibility protocol. It must not be
  promoted automatically to a v2 current authority.
- Canonical v2 selection assigns every candidate one explicit role:
  `normative_source`, `authority_source`, `implementation_input`,
  `lifecycle_projection`, `derived_context`, `execution_evidence`, `report`, or
  `ephemeral_attempt`. Only the first three roles are authorization inputs.
- v2 computes distinct `sourceSelectionHash` and `sourceContentHash`.
  Selection binds roles, repository-relative paths, modules, scope, and resource
  sets; content binds the current bytes of the selected paths.
- The adapter owns transport planning, page ranges, continuation validity,
  coverage, and truncation. A bounded-lossy summary is not truncated when the
  adapter has proven complete coverage.
- A ready receipt is published only as an immutable generation under
  `skill-input-generations/<binding-hash>/`. A validated non-authorizing current
  pointer is atomically advanced after generation validation. Consumers resolve
  only that pointer, never mtime, filename suffixes, or directory scans.
- Knowledge exposes independent execution, publication, and semantic-review
  gates. Knowledge self-change is derived from the changed-set and canonical
  Knowledge path policy, never supplied by a caller flag.
- Attempts use leases and heartbeats. Retention protects the current pointer,
  lifecycle/authorization/terminal references, and unexpired active attempts.
  Deleting committed evidence requires explicit maintainer approval and a
  non-authorizing cleanup receipt.

## Implementation clarification (2026-09-10)

The v2 consumer request explicitly maps operation-required contract selectors
to file/directory roots. A source hash alone does not prove required-input
coverage. Normalized input mappings and complete typed directory membership
are verified before preparation and again when reading current.

The bound authority envelope supplies a full `skill_input_baseline` Git commit.
The adapter observes changed paths and current bytes against that ancestor;
caller changed_paths can only assert agreement, never define the candidate.
Untracked and ignored Knowledge changes remain review inputs. Only runtime
logs, attempts and dedicated Skill-input output storage are outside candidate
authority. Absent Git/baseline facts fail closed.

Live Skill-input gates require v2 pointers. Explicit historical CLI replay
cannot produce a live gate input. Consumers that adopt the shared gate acquire
immutable native-use custody and durable retention registration before context
handoff. These records protect generation lifetime without granting lifecycle,
authorization, terminal or acceptance authority. They do not impose governance
on a separate runtime that does not adopt Skill-input.

The existing consumer context budget is enforced independently of transport
coverage; complete delivery does not permit oversized context publication.

## Consequences

The workflow repair must migrate all consumers to v2 before 8-18 can create a
new current receipt. Existing `skill-input-current*` directories remain
immutable historical evidence until an approved retention action handles them.
This ADR does not create lifecycle authority, publish Knowledge, or start
Bootstrap.

## Relationships

This extends ADR-0048, ADR-0050, ADR-0057, ADR-0058, and ADR-0059. It
supersedes only their v1 Skill-input selection/current-resolution practices.

