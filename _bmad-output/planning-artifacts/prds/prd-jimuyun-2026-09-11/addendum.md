# TC-D1 PRD Addendum

This addendum preserves technical context for `bmad-spec` and
`bmad-architecture`. It is informative and does not add product requirements.

## Existing Assets To Reconcile

- Existing execution-plan directory:
  `execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/`
- Shared replay entrypoint: `scripts/sc/skill_package_replay.py`
- Existing capability descriptor and package-validation receipt schemas.
- ADR-0058 for repository-owned bounded replay and non-authorizing evidence.
- ADR-0060 for Skill-input v2 typed selection, immutable generations, current
  pointers, source/content hashes, baseline-derived changed bytes, custody, and
  retention.
- Round-6 Quick Dev evidence at commit `0dce7806`; useful as implementation
  history but insufficient as rebuilt requirement coverage.
- External review input `docs/fix80501.txt`; informative and non-authorizing. It
  must be preserved in the next candidate tree so the source set is reproducible.

## Architecture Decisions Needed

1. Define the validator adapter interface that proves effective target reads.
2. Define the trust root for validator and semantic-dependency identities so a
   descriptor and implementation cannot drift together undetected.
3. Reconcile producer, schema, and terminal-consumer receipt versions and fields.
4. Define immutable Stable Package and Candidate Package isolation and the six
   case-specific fault injection mechanisms.
5. Define representation, version binding, and terminal closure for the
   maintainer-approved Consumer Manifest.
6. Define Prior Route capture, atomic route transitions, isolated rollback
   exercise, and behavioral equivalence observations.
7. Define Current Snapshot roots, exact source-input restoration, fresh replay
   evidence, and any portable runtime-metadata normalization. No exclusion may
   hide a semantic, target, evidence-validity, or authority input.
8. Define how Exact Cover is generated, validated bidirectionally, and linked to
   runtime evidence without letting generated mappings become source authority.

## Technical Details Deferred From The PRD

- Python CLI subcommands and exact argument vectors.
- Capability JSON and receipt schema field names and version migration.
- SHA-256 manifest algorithms and path containment rules.
- Temporary fixture layout and invalid-package construction.
- Per-case stdout/stderr capture, hashing, and timeout behavior.
- Consumer registry storage and candidate/prior route switching mechanism.
- Quick Dev Q0-Q8 descriptors, runtime edges, snapshot roots, and predecessors.
- Windows launcher behavior and evidence directory naming.

## Current Evidence Gaps To Preserve As Inputs

- Five of six matrix categories currently reuse the same package and capability;
  category presence is stronger than before but does not establish distinct
  stable/candidate semantics.
- Disabled and rolled-back states currently fail closed but do not demonstrate
  execution of a Prior Route by a Consumer.
- Current downstream observations do not bind a complete command/input/output/
  dependency identity.
- Current receipt producer, schema, and historical terminal checks have field
  differences that require one explicit compatibility decision.
- Round-6 covers four repair assertions while the historical requirements
  contain seventeen acceptance assertions; this is the motivating Exact Cover
  gap, not a basis for inheriting the old decomposition.

## Rejected Proof Shortcuts

- JSON output equality without independent semantic execution.
- A target manifest paired with a command that validated another package.
- Validator version read solely from validator output.
- A single empty directory as proof of all invalid-package semantics.
- Different labels over the same fixture, package, or process evidence.
- Configuration state as proof of restored rollback behavior.
- One downstream Consumer as proof of universal compatibility.
- Passing Q8 or historical Acceptance as proof of rebuilt requirements.

## Historical Requirement Disposition

| Historical requirement | Disposition | Rebuilt coverage and reason |
| --- | --- | --- |
| `TC-D1-001` | retained | FR-5 and NFR-5 preserve historical membership and bytes while permitting append-only repair evidence. |
| `TC-D1-002` | retained | FR-1 and FR-2 retain the repository-owned entrypoint outcome and strengthen effective-target proof. |
| `TC-D1-003` | retained | FR-3 and FR-4 retain bounded resolution and receipts while strengthening dependency and execution identity. Only the historical `A05` source-root sub-duty is narrowed under the conditions stated in normative FR-3. |
| `TC-D1-004` | retained | FR-3 and SM-2 retain all fail-closed capability cases and add always-success and dependency drift. |
| `TC-D1-005` | retained | FR-5 preserves the original machine-bound command, native identities, and a bounded current observation. |
| `TC-D1-006` | retained | FR-6 retains the three named repair families and strengthens provenance and counterexample status. |
| `TC-D1-007` | retained | FR-6 preserves non-baseline status; evaluation-set admission remains outside TC-D1. |
| `TC-D1-008` | retained | FR-7 and FR-8 strengthen the matrix from labeled execution to distinct two-sided behavioral comparison. |
| `TC-D1-009` | retained | FR-9 retains the workflow-model-routing observation and places it in the complete Consumer Manifest. |
| `TC-D1-010` | retained | FR-13 requires machine-verifiable non-authority for all derived outputs. |
| `TC-D1-011` | retained | FR-10 strengthens disable/rollback from state rejection to restored Consumer-observed behavior. |
| `TC-D1-012` | retained | Sections 6 and 7 preserve the Phase, runtime, workspace, account, and sandbox boundary and the full historical installed BMAD/GDS forbidden paths. |
| `TC-D1-013` | retained | Sections 6 and 7 preserve TC-E0/D2-D6 separation and exclude Miner, Curator, autonomous changes, ranking, and RL. |

No historical requirement is silently removed. The one-time act of creating
the TC-D1 directory and live Skill-input v1 design are superseded context rather
than requirements in `requirements.v1.json`; ADR-0060 owns current Skill-input
v2 behavior. Initial creation of artifacts that already exist is narrowed to
repair and conformance against the rebuilt FRs.

### Historical acceptance sub-duty disposition

| Historical acceptance | Disposition | Rebuilt coverage |
| --- | --- | --- |
| `A01` | retained | NFR-5 freezes exact historical tracked membership, paths, and content. |
| `A02` | retained | FR-5 and NFR-5 prohibit historical writes and permit only append-only repair paths. |
| `A03` | retained | FR-1/FR-2 retain repository-relative Windows-capable validation of supported packages. |
| `A04` | retained | FR-1/FR-9 require current VDD and Acceptance package routes through the shared capability. |
| `A05` | narrowed | Normative FR-3 retains bounded, non-escaping, non-self-substitutable capability resolution. The historical Skill Creator root remains permitted unless an alternate source is first coordinated under existing owner/ADR authority and receives independent Trust Approval bound to matching content; this revision approves no alternate source. |
| `A06` | retained | FR-2/FR-3/FR-4/SM-5 retain target, validator, version, content, command, probe, exit, and empty-authority provenance and add dependency/trust bindings. |
| `A07` | retained and strengthened | FR-1 through FR-4 and SM-2 retain all old failures and add wrong-target, always-success, and jointly drifted dependency witnesses. |
| `A08` | retained | FR-5 preserves the native command and hashes, records equivalence limits, and forbids authority promotion. |
| `A09` | retained | FR-6 requires the three stable seed identities exactly once with native evidence identity. |
| `A10` | retained | FR-6 rejects missing and drifted seed evidence. |
| `A11` | retained | FR-6 requires the repaired requirement's closed set of non-baseline candidate classifications and forbids accepted-baseline output. |
| `A12` | retained and strengthened | FR-7/FR-8 require two-sided execution, six distinct states, immutable identities, invariants, and non-regression comparison. |
| `A13` | retained | FR-9 requires current workflow-model-routing terminal execution as one observation. |
| `A14` | retained and strengthened | FR-13 requires machine-verifiable empty authorization for all TC-D1 derived evidence and forbids every foreign lifecycle state. |
| `A15` | retained and strengthened | FR-10 requires all current Consumers to observe four route transitions and restored Prior Behavior Baseline. |
| `A16` | retained | Section 6 preserves Phase/runtime/workspace/account/sandbox boundaries and forbids writes to `_bmad/**`, `.agents/skills/bmad-*/**`, and `.agents/skills/gds-*/**`; replay/Consumer repair permission does not override them. |
| `A17` | retained | Sections 6/7 preserve first-class roadmap separation and prohibit promotion, Miner/Curator, autonomous modification, ranking, and RL. |

The `A05` narrowing takes effect for an alternate source only after the
conditions in normative FR-3 are met. Architecture and ADR reconciliation alone
do not constitute Trust Approval and cannot authorize an arbitrary validator
root.

## Normative Constraints Mirrored From The PRD

This section is a design aide and adds no independent requirement. If it
conflicts with `prd.md`, the PRD controls.

- The append-only repair round binds a current Git baseline as a freshness input.
- Replay, seed, matrix, review, and Quick Dev outputs must declare their empty
  authorization set in a machine-verifiable form compatible with current
  repository lifecycle contracts.
- The original machine-bound historical command is retained as an auditable
  fact and cannot become a current executable authority.
