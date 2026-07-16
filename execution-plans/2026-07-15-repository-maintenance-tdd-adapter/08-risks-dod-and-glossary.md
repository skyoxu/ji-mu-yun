# Risks, Definition Of Done, And Glossary

## Risks And Mitigations

| Risk | Mitigation | Stop condition |
| --- | --- | --- |
| Contract becomes duplicate requirement authority | IDs and source refs only; exact source coverage | Any copied normative prose with no owner |
| Stock Quick Dev regains semantic authority | Backend v1 is repository-owned and implementation-only | Backend exposes review/done/commit |
| Plan validator self-authorizes weakened rules | Mutation fixtures and independent Bootstrap review | Same slice weakens its authorizer |
| Dirty tree loses user work | Freeze index/closures and block write overlap only | Overlap or unexplained drift |
| Recovery mutates failed history | Append-only run directories and stale successors | Prior evidence changes bytes |
| Old plans are accidentally promoted | Additive metadata and shadow-only predicates | Existing plan status/book changes |
| P2 deferrals hide material risk | Non-deferrable risk families and expiry blocking | Missing owner, proof, expiry, or closure test |
| Adapter grows into a Router | No provider scheduler or hidden state | New central intent/plan selection logic |
| Historical script directories grow new authority | New Skill owns common execution | New adapter semantics added to `scripts/sc` or `scripts/python` without ADR delta |
| Large validator becomes unmaintainable | Keep files under 400 lines where practical and split by responsibility | Unapproved oversized mixed-concern script |

## Definition Of Done: Plan Creation

- All required books, machine owners, fixtures, validator source, and tests exist.
- Every active requirement maps once to source, owner, first phase, acceptance ID, evidence intent, and status.
- Source coverage includes all nine `agentbuild.txt` sections and every clarification decision.
- Deliberate invalid and mutation cases fail with their expected stable rule IDs.
- Validator unit tests and the fresh composite command pass.
- The current result envelope has matching candidate/source/validator hashes and exact authority sets.
- Status is `plan-ready` only after the draft candidate produces valid plan-ready evidence.
- No implementation, old-plan backfill, ADR, standard, Skill, or Bootstrap runtime change is falsely claimed complete.

## Definition Of Done: Future Implementation

- Framework ADR accepted.
- Common schema has one Skill owner.
- Self-hosted TDD lifecycle and recovery evidence pass.
- Three shadow backfills pass without authority changes.
- Bootstrap review is finalized under current hashes.
- No open accepted P0/P1; every accepted P2 is disposed; high-risk and expired deferrals are absent.
- Plan-local validator authorizes implementation acceptance and explicitly excludes release.

## Glossary

- **Slice Capsule**: compact, hash-bound input given to an implementation-only backend.
- **Implementation contract**: per-plan machine projection of slice IDs, paths, commands, evidence, and predicates.
- **Execution read set**: files whose content influences execution but is not necessarily modified.
- **Dependency closure**: transitive files/contracts required to interpret or validate the slice.
- **Shadow backfill**: additive, non-authoritative contract and fixture projection onto an existing plan.
- **Disposition**: fixed or validly deferred resolution of an accepted P2.
- **High-risk P2**: advisory-severity finding in a non-deferrable security, data-loss, authority, evidence-integrity, irreversible-mutation, or release-bypass family.
