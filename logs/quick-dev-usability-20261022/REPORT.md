# Quick Dev usability maintenance, 2026-10-22

Implementation commit: cfae69b40b6608d85c2c86f7efd1537c87d41e0c.
Comparison baseline: 68968f53699c2b74f3c2087a7f0847ade9532fad.

The maintainer authorized implementation after rechecking the optimization
findings. Scope: partial obligation outcomes, complete-session preflight,
bounded deterministic native progression, and static selector diagnostics.
The .NET/TRX helper remains deferred to pre-S2. No Package A Acceptance was run;
ADR-0062 adoption remains a separate decision.

## Implemented behavior

- Mixed passing and expected-failing cases within one obligation retain all
  cases, route to missing, and require exact probe-to-RED outcome continuity.
  Uniform missing probes cannot silently become partial RED. Passing-only
  assertions contribute no invented expected failure ID. Successors require
  all bound cases to pass.
- Read-only preflight validates explicit source/base commits, profile, all eight
  snapshot-root kinds, input existence, paths, output collisions, planned inputs,
  and complete slice/dependency ordering before a long run.
- A frozen explicit request drives existing stage, reentry, Q7 and Q8 owners.
  Bounded calls pause for RED authoring, Q4 implementation and refactoring via
  existing local or caller-session routes. The adapter invokes no model. Failed,
  stale and interrupted evidence remains immutable and blocking.
- Selector inspection explains static narrowing/fallback, full terminal argv,
  Q6 commands and duplicate declarations. Literal IDs and simple classes are
  supported; unsupported mappings keep the declared selector. Terminal and
  required Q6 tests retain their full scope.
- The produced Acceptance binding was read by the real current handoff consumer.
  This validates the handoff shape; it is not product Acceptance.

## Fresh validation

The temporary environment lost the prior unpushed checkout and logs. Source was
reconstructed from repository baseline and available transcript material. The
old 121-test result is NOT reused as proof. All results below were actually rerun.
FastCtx was not attached; Linux shell/Python was the explicit fallback.

- First new partial-case tests against unchanged baseline: 4 failed, 3 passed.
- Final targeted run: 130 passed in 32.01 seconds.
- Full Quick Dev suite: candidate 411 passed, 21 failed; baseline 374 passed,
  21 failed. Exact FAILED/SUBFAILED identities match; no candidate-only failure.
- Existing failures include historical Skill-input fixtures, Windows `py`,
  absent local Codex configuration, worktree index assumptions, and existing
  fresh-medium VDD/Q6 consumer fixtures. They were preserved, not waived or fixed.
- Skill Creator's quick_validate.py: Skill is valid.
- An intermediate combined run caught a CLI exit-code compatibility change.
  It was narrowed to the new session actions, then the full targeted set passed.

Run command: PYTHONDONTWRITEBYTECODE=1 with the installed test dependencies in
PYTHONPATH, python3 -B -m pytest -q -p no:cacheprovider. The targeted files are
execution_session, partial_obligation, case_selection, cer_behavior_routing,
cer_case_evidence, ch456_stable_runner, stage_reentry, runtime_stage_pipeline,
and coverage_predicates under the Quick Dev tools/tests directory.
Full-suite commands use that entire tests directory on each explicit checkout.

## Public-entry forward runs

A separate forward-test agent used disposable repositories and the unpatched
public scripts/quick_dev/run.py entry, real child pytest processes and current
native evidence writers. No network/model worker was required. Raw invocations,
source manifests, fixture inputs and receipts are in forward-evidence.tar.xz.

- All-present fixture: bounded pause/resume reached native Q8 with three process
  receipts and no RED. Repeated completion retained evidence byte-for-byte.
- Partial fixture: AS-2 had one passed and one expected failing parameter case.
  Actual probe and RED were followed by public Q4 handoff/finish, GREEN,
  caller-session no-op refactor, regression and Q8. Six process receipts and
  exact closure were retained on replay.
- Interrupted fixture: actual termination during probe left incomplete evidence.
  Both subsequent calls returned nonzero blocked results without rewriting it.
  This proves safe interruption handling, not successful mid-stage recovery.
- The first three copies preceded the narrow CLI exit-code compatibility fix.
  Their only source difference is captured in source-comparison-final.json;
  the exact old stable_runner is archived as source-overlay/early-stable_runner.py.
  Fresh updated-present and updated-interrupted fixtures match final source and
  verify completion/replay and blocked exit behavior after that correction.

The forward agent hit its usage limit after writing the raw records and computed
summary. The parent inspected those records and wrote this report; no missing
agent narrative or historical output was substituted for execution evidence.

## Evidence and limits

forward-archive-manifest.json binds the 270 archived files. Copied shared runtime
sources are referenced by their per-file SHA256 manifests and implementation
commit rather than duplicated in the archive. source-hashes.json binds the final
Quick Dev sources. validation-evidence.tar.xz preserves raw test output, including
intermediate failures; suite-comparison.json identifies every baseline failure.

Linux fixture execution does not establish Windows ACL, real .NET/TRX execution,
actual online model-provider operation, or full 8-06 product Acceptance. Prior
8-06 Q8 proof remains bound to its original runtime; updated handoff notes require
normal native evidence refresh before future formal Acceptance.
