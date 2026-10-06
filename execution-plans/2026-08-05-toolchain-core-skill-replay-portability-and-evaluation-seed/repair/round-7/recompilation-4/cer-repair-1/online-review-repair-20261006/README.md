# Online Review Repair: Local Verification Handoff

Candidate predecessor: `e289d7d3f8572595ca28c498adc798d1fa2a2bf7`.
Authority: Accepted ADR-0058, its bounded execution binding addendum, and
ADR-0060. This is a direct implementation repair. No formal VDD, Quick Dev,
Acceptance or live backend was executed online.

## Repaired behavior

- Effective target reads come from the validator child, not wrapper enumeration.
- Detached positive/negative Probes use the same location and an explicit defect
  oracle; wrong diagnostics and infrastructure failures cannot become success.
- Validator/source/descriptor/resources are checked against immutable Git bytes.
- Matrix v3 freezes Stable provenance and Candidate identity, executes both own
  replay entries, and runs six distinct native fault/recovery scenarios.
- The frozen Consumer set reconciles Python call surfaces and the Knowledge
  workflow's two existing package command factories. Every applicable Consumer
  runs enable, disable, rollback and re-enable, including invalid-package calls.
- Snapshot v2 binds repository dependencies, runtime/environment and candidate
  bytes; fresh checkout restores the complete pinned input set before replay.
- Raw archive preflight lists missing native roots and untracked evidence. It
  does not repair missing bytes or publish a lifecycle result.

## Windows verification

Sync this branch without overwriting local evidence or user changes. From the
repository root, run the new stdlib regressions first:

```powershell
py -3 -B -m unittest discover -s scripts/sc/tests -p test_skill_replay_review_regressions.py -v
```

Then run the existing relevant selectors with the real installed pytest:

```powershell
py -3 -B -m pytest -q scripts/sc/tests/test_skill_package_replay.py scripts/sc/tests/tc_d1_cer
```

Retain stdout, stderr, JUnit and command/HEAD records in a NEW directory under
`logs/08-05-real-skill-replay/`. Report all failures and collection errors; do not
exclude failed cases, rewrite old receipts or silently downgrade their asserts.
The online environment lacked pytest; its full selector suite is unverified.

The checked-in historical v2 Matrix must remain unchanged. A new native v3 input
can be prepared and run explicitly:

```powershell
py -3 -B scripts/sc/skill_package_replay.py prepare-matrix --target .agents/skills/run-refactor-implementation-acceptance --capability scripts/sc/config/skill-package-validator-capability.v1.json --stable-commit e289d7d3f8572595ca28c498adc798d1fa2a2bf7 --output logs/08-05-real-skill-replay/online-repair-windows-1/matrix.json
py -3 -B scripts/sc/skill_package_replay.py replay-matrix --matrix logs/08-05-real-skill-replay/online-repair-windows-1/matrix.json
py -3 -B scripts/sc/skill_package_replay.py replay-package --target .agents/skills/run-refactor-implementation-acceptance --capability scripts/sc/config/skill-package-validator-capability.v1.json --probe-mode fresh
```

Use a new output directory on another attempt; preparation is append-only. Keep
the default existing-validator Git input. Do not repin it to the repaired HEAD
to bypass a drift failure. Alternative validator and Consumer exceptions require
their actual C3 approval; this repair does not supply that approval.

## Archive the original native run

The previously pushed Q8 references local raw runs that were absent on GitHub.
Audit those original bytes, without editing them:

```powershell
py -3 -B scripts/sc/audit_skill_replay_archive.py --result execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1/quick-dev-ready/current-run/terminal-incremental-20261006/implementation-complete-result.v2.json --output logs/08-05-real-skill-replay/online-repair-windows-1/original-archive-audit.json
```

Inspect `missing_paths`, `identity_mismatches` and `untracked_archive_paths` in
the audit document. Recover missing bytes only from the original local native
run. Force-add only the exact reviewed paths, including stdout/stderr, binary
observations, descriptors and runtime edges. Preserve their original locations
and content. A successful archive audit is archival completeness, not a current
candidate validation or Acceptance pass.

## Current evidence and closure

These production/test/schema changes make the old snapshot-bound Q7/Q8 stale.
After Windows checks pass, bind the affected plan selectors to the new native
Matrix/snapshot contracts and produce fresh affected Q7 plus current Q8 using
the owning local workflow. Retain unaffected evidence only if the owner proves
its current identity/closure remains valid. Do not rerun unrelated slices by
habit or invent receipts. Do not claim the old `implementation-complete` result
certifies these new bytes.

C3 remains OPEN. Original PRD/Spec/source brief, historical plan inputs, failed
runs and prior Q7/Q8 were not rewritten. Formal Acceptance eligibility remains
pending local verification, complete raw archival and current owner evidence.
