# CER execution-contract repair candidate

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
