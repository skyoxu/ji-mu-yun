# Evidence And Freshness

Store mutable run evidence below `logs/tdd-adapter/<plan-id>/<slice-id>/<run-id>/`. Keep plan contracts, schemas, fixtures, and predicates version controlled in their owning plan or Skill.

Every stage binds the current slice identity and validator identities. Slice identity covers the selected slice plus its recursive declared predecessors; a later independent-slice repair does not stale earlier slice evidence. Candidate evidence also binds the authority, source, command registry, Git baseline, declared write boundary, stage results, and predecessor lineage. Any mismatch inside that closure invalidates the result.

Failures are preserved. A successor references the stale predecessor, its exact observation hashes, execution fingerprint, candidate identity, and next transition; it does not copy observations or inherit authorization from the stale run. Identical protocol closure is replayed; a different closure creates a new successor attempt and never overwrites immutable artifacts.
