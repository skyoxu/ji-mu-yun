# Cross-slice execution evidence repair

## Isolation and baseline

- Remote main was resolved by `git ls-remote origin refs/heads/main` to
  `a1e783c569cb5a78ea8728c83518fd13c73a99e8`.
- Worktree: `/workspace/evidence-reuse`; branch: `fix/cross-slice-evidence-reuse`.
- The supplied host `127b26a4a22bcd97a4231296c471d06a3548521f` was not local;
  read-only fetch returned `upload-pack: not our ref`. The production branch
  was not advertised. Fetching the known verification branch for inspection
  also did not make that host available. No verification-branch commit was
  merged, cherry-picked or copied into the repair.
- The original `/workspace/ji-mu-yun` worktree and production work were not
  edited. Its pre-existing status entry also appears on a fresh main checkout:
  the tracked CRLF blob conflicts with its LF attributes. The fresh worktree
  file bytes equal HEAD exactly (SHA256
  `4bfa9206a23122810ec7c41783ce8c6866d91917ab1633a795891a2937c596d9`).
  That file is excluded from the repair commit and patch.
- No new requirement/plan directory, BMAD reviewer, A/B run, model selection,
  production resumption, push, PR, merge or CI monitoring was performed.

## Minimal plan and self-review

The existing Q6 gate accepted only its slice's primary receipt. Process/case
reports and terminal edges bind run/descriptor identity, so rewriting receipt
identity or weakening reentry would break the proof chain. The bounded repair
adds an explicit content-keyed original registry and non-executing uses,
retains original report identity, and updates the existing readers together.
VDD owns existing coverage/dependency declarations; Quick Dev augments them
with conservative content and observed dependency inventories. No compiler or
planning workflow is executed.

Self-review checks: original immutability; no successful publication for
failure/timeout/skip/unknown dependencies; exact argv/cwd and actual case cover;
OS/interpreter/environment isolation; original reread at Q6/Q7/Q8 and recovery;
no terminal predicate bypass; repeated request seals; safe legacy rejection.

## Changed owners

- VDD Skill: clarify content freshness, coverage/dependency ownership and
  shared terminal proof without importing execution authority.
- Quick Dev Skill/references: versioned reuse semantics and compatibility.
- shared_execution.py: repository/environment/semantic fingerprints, exact
  key lookup, original hashes, reference projections, request/completion seals,
  observed-dependency admission and explicit rejection reasons.
- pytest_case_collector.py: bounded Python-visible reads/imports and unsupported
  external effects. These observations do not change test verdicts.
- stage_pipeline.py and regression_gate.py: shared execution entry for primary
  stages, compatible Q6 commands and terminal.
- case_evidence.py, coverage_predicates.py, stage_reentry.py, recovery_resolver.py,
  independent_judge_v2.py and runtime_evidence.py: validate original identity,
  current inputs, use classification and actual assertion coverage.
- test_shared_execution.py: deterministic local tests, including the native
  dispatcher/Q7/terminal/Q8 closure and missing-original rejection.
- ADR-0041: record the narrow authorized execution-reuse decision.

## Verification

Python dependencies were installed in `/tmp/evidence-reuse-venv` only. The
system Python lacked pytest. No real model was invoked. Final broad run:

```sh
PATH=/tmp/evidence-reuse-venv/bin:$PATH python -m pytest -q \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_shared_execution.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_reentry.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_cer_behavior_routing.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_cer_case_evidence.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_coverage_predicates.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_runtime_stage_pipeline.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_full_lifecycle.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_skill_contract.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_stage_recovery.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_recovery_mutations.py \
  .agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_q6_regression_gate.py \
  -k 'not test_standard_q6_runs_explicit_single_file_consumer_fixture'
```

Result: 134 passed, 1 deselected, 6 subtests passed in 113.10 seconds
(`final-tests.txt`). The final diagnostic-only hardening adds one negative test;
its affected-suite recheck passed 45 tests in 88.31 seconds (`final-recheck.txt`).

Package validation:

```sh
/tmp/evidence-reuse-venv/bin/python -B .agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py --skill-root .agents/skills/vdd-execution-plan
/tmp/evidence-reuse-venv/bin/python -B -m unittest discover -s .agents/skills/vdd-execution-plan/scripts/tests -p test_validate_skill_contract.py
```

Results: package checks all passed; 22 tests passed. `git diff --check` passed
for repair paths. Historical failed diagnostic outputs are retained locally.

The one deselected historical integration test was actually attempted before
exclusion. It launches `test_plan_directory_loop.py`; that suite produced
47 passes and one failure because its legacy `read_only_index_tree` requests
`tempfile.mkdtemp(..., dir='/')`. The filesystem returned `Errno 30: Read-only
file system`. This is an environment failure, not an auto-review rejection.
No root write was retried with escalation and no historical implementation was
changed. See `legacy-loop-diagnostic.txt` and `initial-tests.txt`.

## Reuse and rejection examples

- Same selected module, same inputs, another slice/terminal: one original
  process, references with `process_attempts=0`, unchanged original report ID.
- New Git commit with identical file contents: reuse succeeds.
- Changed implicit_helper.py: `reuse-dependency-content-changed:implicit_helper.py`.
- Windows versus Linux: `reuse-environment-changed:system`.
- Missing/tampered original: `reuse-original-invalid` with the original path or
  artifact-integrity reason; Q8 cannot publish completion.
- Unbound real reads/imports or child/network effects: explicit non-publication
  reason, normal execution remains available. No synthetic success is cached.

## Compatibility and verification limits

Apply the producer and readers together. Existing receipts remain historical;
no missing content/dependency identity is backfilled and no old receipt is
relabeled. Only a new eligible execution can seed the shared registry.
Same-run immutable identity remains strict; cross-run reuse is an explicit use.

This is an exact-argv controlled Python pytest boundary, not arbitrary selector
subsumption or a hermetic execution system. Repository-wide conservative
inventory can invalidate unrelated edits. Excluded evidence/plan files must be
explicitly bound if consumed; observed missing read bindings reject publication.
Real child processes/network calls are conservatively ineligible because their
transitive inputs are not observed by this collector. Concurrent cross-process
coalescing is not implemented.

No original r40 receipt, full 738-case consumer suite, real BMAD model, Windows
host, production task acceptance or integration onto the supplied inaccessible
stable host was verified. In particular this repair does not claim that the
original expensive suite is eligible without checking its observed dependency
boundary. The independent patch is based solely on main and contains no
unfinished requirement implementation. Stop after local delivery; original task
resumption and integration require a later user instruction.
