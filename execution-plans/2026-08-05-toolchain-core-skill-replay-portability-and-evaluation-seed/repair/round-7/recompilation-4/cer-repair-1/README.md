# CER execution-contract repair

## Current handoff: Quick Dev ready

Use [quick-dev-ready/START-QUICK-DEV.md](quick-dev-ready/START-QUICK-DEV.md)
and its `current-plan/` successor for new Quick Dev work. The canonical CLI
published this execution-only repair of the reviewed 114-obligation, 45-slice
plan. The continuation instructions below are retained as historical repair
context; do not rerun their compilation commands to start implementation.

The successor preserves source meaning and records the predecessor source-byte
identity correction, test bindings, write boundaries and behavior RED routing.
It is planning readiness, not implementation or Acceptance completion.

## Current continuation: selective V3 cache repair

This section supersedes the new-input compilation command below for the reported V3 selector failure. Do not continue the interrupted `compiler-requirements.md` attempt merely to repair old V3 selectors. Retain that attempt and its partial progress as historical.

The repository V3 group repair now retains individually valid contracts from an invalid cached chunk and requests only its invalid obligation IDs. The worker receives the rejected missing selector names as diagnostic context, not authority to create arbitrary files. Existing domain, path, expected-red eligibility and V4 checks still apply. Prior invalid cache bytes are retained in sidecars.

In the local checkout, locate the **original failed attempt** that produced the c3f814e2 V3 error. Verify its source index refers to the original `recompilation-4/assembled-requirements.md`, and retain that attempt's `.compiler-cache` and `.compiler-work`. Those uncommitted files are not available remotely, so no exact local attempt path or cache-hit count is asserted here. Do not use the interrupted new-input attempt or mix caches across input identities.

Resume through `scripts/vdd/compile_plan.py` using that original requirements path, that same original failed `--out-dir`, its original profile/companions, and `--resume-from first-failed-stage`. Write the new `--result-json` to a fresh path under `logs/08-05-real-skill-replay/`. Do not pass `--worker-cache`: that option is explicit fixture injection, not ordinary resume, and clears the disk replay cache.

V0/V2 and other deterministic checks may run again; unchanged V1 worker calls use their existing matching caches. This is not a V3-only bypass. If an unrelated V1 request actually launches, stop and compare its input/cache identity instead of deleting caches or widening the source. If the original failed attempt/cache is unavailable, this targeted recovery cannot be promised; preserve the evidence and report that specific gap.

Only a real canonical result can grant plan-ready. The online tests exercise the repair orchestration with a fixture backend; they do not run the private local attempt or live semantic workers. C3 stays OPEN, authorizes=[] and current-run evidence must be rebound after actual publication.


Base commit: `b4d922a9c4a0cd87741fef7b1a35bfc33431260f`.

This candidate addresses the blocked Quick Dev handoff. It does not publish a plan-ready result, authorize production changes, or claim runtime verification. The original current-plan and current-run evidence remain unchanged.

## Changes

- Preserve all 114 obligations and Acceptance semantics, and all historical failure intents.
- Add 29 expected-red intents only for eligible behavior/quality, non-Governance obligations. Existing integrity and governance failure routes remain intact.
- Declare 41 dedicated test-author entries for S2 through S42. These are planned files, not fabricated tests or marker evidence.
- Remove production-owner/execution-snapshot intersections in S6, S14, S15, S17, S22, S24, S30, S39 and S41. Production ownership remains declared.
- Rebuild related failure references, coverage, contexts, routing and input identities.

Missing CER markers alone are test-authoring work. They must not be treated as evidence of missing product behavior. A probe must distinguish present, legitimate behavior RED, and unverifiable infrastructure or binding failure.

## Local continuation

1. Synchronize this branch. Run `py -3 execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1/verify_candidate.py` from the repository root. This checks candidate structure and preservation only.
2. Use the repository VDD skill and canonical compiler to validate and publish a repaired plan from this candidate. Preserve C3 OPEN and `authorizes=[]`; do not hand-edit a plan-ready state or bypass compiler stages.
3. Bind a new Quick Dev attempt to the newly published bundle. Preserve `logs/quick-dev-current-run-20260914`. S1 is unchanged, but its old receipt is not automatically valid under a different bundle identity.
4. Author genuine tests at the declared dedicated entries, starting with S2 and S3. Do not reuse old S2 markers as proof that the new entry was authored. Bind exact assertion IDs and emit the bound expected-red failure ID only immediately before the corresponding real assertion failure. No unconditional failures, skip/xfail, or synthetic receipts.
5. Freeze the authored tests and run actual probes. Reuse neither S2-repair4 failure receipts nor its old failure-ID mapping. Infrastructure failures, timeouts and missing markers stay unverifiable. Already-present behavior must not be forced RED.
6. Continue remaining slices only after valid routing. Q8, terminal validation and formal Acceptance remain pending.

The in-session JavaScript static checks are listed in repair-summary.json. Python, canonical compilation, author-red and runtime probes were not executed online. C3 decisions and all original protected boundaries remain in force.

## Selector repair after c3f814e2

The archived compiler result is a V3 execution-contract rejection, not a failed production test. Its hint indexes are generated V3 indexes, not S36/S37/etc. The two absent names are `scripts/sc/tests/test_evaluation_seed_manifest.py` and `scripts/sc/tests/test_detached_probe_execution.py`.

Neither absent name occurs in the versioned candidate bundle. The failed local worker output/cache was not committed, so this repair cannot claim to replay those exact eight hints. Editing the published slices alone would not change the canonical compiler's V3 input.

Use `compiler-requirements.md` as the explicit replacement compilation input. It retains every byte of the original assembled requirement sections and adds execution metadata derived from this candidate's actual obligation/slice mapping. It declares the exact planned author entries with the repository's existing `must create` syntax and identifies existing fixture paths. It does not create placeholder tests, alter an oracle, relabel a constraint as expected-red, or grant C3 approval.

The input intentionally binds all affected source sections, because the new worker's hint numbering and grouping are not stable IDs. New source identity requires fresh compilation; do not use the old V3 cache as an approved output. Do not compile the old assembled source alone or pass both sources as companions (their requirement IDs would be ambiguous).

Run from the repository root:

```text
py -3 scripts/vdd/compile_plan.py --requirements execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1/compiler-requirements.md --out-dir execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1/canonical-selector-repair/current-plan --profile self-hosted --result-json logs/08-05-real-skill-replay/selector-repair-20260915/compiler-result.json
```

The output directory is a new attempt inside the same repair target; it preserves prior failure evidence. If that exact attempt subsequently fails, inspect its first failure and use the canonical resume option only after repairing its cause. Preserve any locally required governance/input selection conditions.

Only the canonical process may publish plan-ready. The prior candidate remains repair-vdd. After a genuine plan-ready result, bind Quick Dev to the new bundle and regenerate current-run probe evidence. Existing test presence is not coverage proof; the planned per-obligation assertions still require real authoring and execution.

Online checks are recorded at `logs/08-05-real-skill-replay/selector-repair-20260915/input-validation.json`. These are source/identity/path checks and execution of the repository's explicit-source parsing function in isolation, not a full VDD invocation or production tests.
