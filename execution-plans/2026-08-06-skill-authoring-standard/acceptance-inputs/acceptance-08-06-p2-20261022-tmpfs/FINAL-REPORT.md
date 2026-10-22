# 08-06 Package A: five-P2 repair closeout

Status: formally accepted for the new candidate on 2026-10-22.

- Branch: `fix/08-06-skill-authoring-plan-refresh`. No merge.
- External-review / repair baseline: `b9eba90549beaf0f470fa68562144f4d68e27c18`.
- Product commit: `7b3bb1ce83637c718c2b9fc71d565409fb17fead`.
- Acceptance candidate with frozen consumer inputs: `11590e6616f86cd8f2d3bea5dcd2a6316df4c2e2`.
- Original plan baseline retained: `f7ac19dbc1dde82e73f91854b5dc0c157c78703a`.
- Formal run: `acceptance-2677f519e0491a3c`. Coordinator `completed`; owner finalization `acceptance-passed`.

## Exactly five fixes

| Boundary | Minimal change | Added parameter cases |
| --- | --- | --- |
| Public dependencies | Require an explicit list; an explicit empty list stays valid | 6 |
| Owned-schema regex | Convert invalid regex compilation into existing structured error / exit 2 | 4 |
| Optional authority | Fallback only for valid contained missing authority; invalid paths, malformed JSON, wrong identity and directories fail | 12 |
| Capability owner | Reuse substantive-text checking only for owner in the seven primary capability declarations | 14 |
| Frontmatter | Validate single-quote pairing within the existing supported subset; doubled quotes remain valid | 6 |

Production changes are limited to `scripts/sc/validate_skill_quality.py` (16 changed lines). Tests append 144 lines to `scripts/sc/tests/test_skill_quality_core.py`; all previous test bytes are preserved. Both API and actual CLI are exercised in strict and inventory modes. Positive controls include explicit empty dependencies, legitimate optional missing fallback, valid owners and doubled single quotes. No original requirement, standard version, ADR adoption state, compiler, Quick Dev runtime, Acceptance runtime or Package B implementation changed.

## Actual verification

| Native stage | Result |
| --- | --- |
| New counterexample RED, S13-R1-R1 | 36 real failures and 111 passing cases; native expected-red |
| Frozen GREEN | 147 passed |
| REFACTOR selector / required regression | 147 passed / 312 passed |
| Current Q7 and terminal | All 31 slices refreshed against actual shared validator and fixture dependencies |
| Whole-plan Q8 | implementation-complete; 31 predecessors and 578 runtime closure tuples |
| Formal Package A suite | 398 passed; 378 existing custom-marker warnings in plain pytest mode |
| Formal Acceptance regressions | 21 passed |
| Formal registered actions | All six completed with exit code 0 |
| Registered verify_current_handoff | pass; implementation-complete; 31 slices; 578 tuples |
| New formal Acceptance | acceptance-passed, never inherited from the b9eba905 run |

Native authority paths:

- Q8: `logs/08-06-p2-repair-20261022/closure-r2/implementation-complete.json`.
- Current binding: `logs/08-06-p2-repair-20261022/closure-r2/acceptance-current-quick-dev-binding.json`.
- Coordinator: `execution-plans/2026-08-06-skill-authoring-standard/acceptance-inputs/acceptance-08-06-p2-20261022-tmpfs/coordinator-result.v3.json`.
- Final verdict: `execution-plans/2026-08-06-skill-authoring-standard/acceptance-runs/acceptance-2677f519e0491a3c/finalization/acceptance-passed.v1.json`.
- Current handoff process receipt: `execution-plans/2026-08-06-skill-authoring-standard/acceptance-runs/acceptance-2677f519e0491a3c/actions/acceptance-current-q8-read-only/attempt-001/result.json`.

The two existing A06 assertion identities own the added API/CLI counterexamples; each defect also checks its domain diagnostic. Native Q2 freezes them. No semantic-plan repair or compiler change was necessary. All 31 Q7 proofs were refreshed because their actual snapshot roots include shared changed sources; refresh scope was not assumed to be five slices. Present behavior used native regression; no synthetic RED was introduced.

## Preserved failures and environment recovery

All attempt records are retained and explicitly non-successful where applicable:

1. An initial author attempt selected the unavailable default CLI route. The explicit host-session route was then used.
2. An editing mistake during parameter conversion removed old test content in a preliminary probe. The complete old content was restored before the successful formal RED; final diff is append-only for tests. The blocked probe remains historical.
3. One Q7 refresh detected concurrent creation of Acceptance input files as repo-noise; the affected run and closure input were replaced with fresh explicit successors, not overwritten.
4. Restored historical untracked evidence blocked commit-mode projection. Those files were retained with hashes outside the clean candidate checkout; current required evidence remains in the proof archive.
5. Initial projection hit a cross-device atomic-move error. Preparation TMPDIR was moved onto the candidate filesystem without changing gates.
6. `acceptance-cb9fd8c39325169d` failed because the controlled environment could not lazily fetch a declared historical Git trust object. The immutable e289d7d3 baseline was hydrated; native trust validation checked 123 semantic dependencies.
7. `acceptance-08-06-p2-20261022-git-recovery` failed on cross-device test fixtures (12 failed / 9 passed).
8. `acceptance-08-06-p2-20261022-fixture-recovery` retained a directory-exists fixture failure (1 failed / 20 passed). The unchanged suite passed 21/21 in fresh tmpfs fixtures.
9. The final registered inputs explicitly bind same-device tmpfs fixture paths. The new coordinator reran all six actions and published its own verdict. No old failure or acceptance status was relabeled.

No old dirty worktree was changed. The isolated checkout kept committed bytes, including a file-specific local Git attribute needed to avoid a false mixed-newline status difference. Environment adjustments did not change source or normative contracts.

## Limits and replay

This is Linux/Python static Package A verification, not Windows ACL, Godot, live service, Package B or deployment verification. The Knowledge catalog remains stale; the canonical adapter allowed degraded catalog freshness after verifying and refreshing the selected current-worktree read-set. No Knowledge publication was performed.

The complete fresh proof and unsuccessful attempts are packaged under `logs/08-06-p2-repair-20261022/artifacts/`. Verify the archive and per-file hashes in `evidence-manifest.v1.json`, then restore repository-relative members before native read-only replay. The archive preserves exact bytes, including objects published directly for navigation. Git history supplies the original product baseline and trust commits. Formal Linux command descriptors use their recorded interpreter and tmpfs paths; another environment must create its own valid execution inputs, not relabel these receipts.

Historical b9eba905 archives and final verdict remain untouched in Git history. No merge, Package B, broad refactor, new governance or normative-version change was performed.
