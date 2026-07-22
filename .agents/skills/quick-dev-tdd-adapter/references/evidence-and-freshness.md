# Evidence And Freshness

Store mutable run evidence below `logs/tdd-adapter/<plan-id>/<slice-id>/<run-id>/`. Keep plan contracts, schemas, fixtures, and predicates version controlled in their owning plan or Skill.

Every stage binds the current contract and validator identities. Candidate evidence also binds the authority, source, command registry, Git baseline, declared write boundary, stage results, and predecessor lineage. Any mismatch invalidates the result.

Failures are preserved. A successor references the stale predecessor and starts with a new current snapshot; it does not inherit authorization from the stale run.
