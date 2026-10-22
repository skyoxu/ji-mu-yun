# Dependency Atomic Repair and Online S3 Execution

Authority: ADR-0041. This is separately authorized delivery-tool maintenance
plus a bounded Package A implementation, not Package B migration.

## Actual root causes

The retained first S3 probe executed four real cases: three missing dependency
diagnostics failed while the no-execution case passed. One coarse obligation
could not represent that mixed state. A second expected-red ID described a
harness failure, incorrectly requiring two unrelated failure IDs in each case.
The new authored split gives each independent outcome its own Acceptance.

The published-repair path exposed four reusable compiler defects:

- V1 split admission was hard-coded to FR-6 and exactly two children. It now
  binds one exact active predecessor/source and rejects invalid, colliding,
  cross-source or incomplete replacements. V4 and downstream gates remain.
- Predecessor admission verified entries-only identity even when V0 emitted
  entries-plus-companions identity. The declared full hash shape is now checked.
- A shared planned pytest module partially authored by Q2 blocked every future
  slice. Only nonempty markers assigned by this same plan to this same frozen
  file may now admit further Q2 authoring. Unknown/empty/wrong-file mappings
  remain blocked; runtime case coverage is never inferred.
- Rehydration recomputed individual Acceptance metadata from merged slice
  owners. It now preserves each Acceptance's published preflight metadata; the
  unselected-drift gate remains strict.

The failed published successor attempts are retained; no failed candidate was
promoted by editing evidence or relaxing final gates. Final public result:
`logs/08-06-dependency-plan-repair-20261020/compiler-result-04.json`.

## Verification and current limits

85 targeted VDD/handoff tests passed, including real 8-05 predecessor coverage
and new 8-06 source-bound split, companion tamper, partial-module and metadata
checks. 42 Quick Dev case/first-use gate tests passed. The VDD Skill's 10 package
checks passed. Compiler source recall reported 289 supported active obligations,
zero invented items and zero source gaps; all 25 slices retained their IDs.

Online S3 reached native slice-ready after genuine probe/RED, bounded production
implementation, GREEN, REFACTOR and present-regression. Q6 also executed A09
and all three current migration cases. Frozen tests were not changed by the
production worker. See `logs/08-06-dependencies-20261020/README.md`.

This does not complete Package A. Policy/schema/standard/public-entry work and
most declared behavior remain. No whole-plan terminal, Q8 or Acceptance result
is claimed. See the active LOCAL-HANDOFF for remaining contract concerns.

## Sibling disposition

The separate execution-only handoff publisher also has entries-only source-index
hashing. It was not invoked or changed in this bounded published-semantic repair;
case-section handoff-only publication needs that producer/consumer identity
alignment before use. No unrelated review/worker/backend or Phase behavior was
changed.
