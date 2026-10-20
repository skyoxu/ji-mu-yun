# VDD execution stability repair

Base: `57b00012057ac565c3ab964d6fa18d7053825408` on
`fix/08-06-skill-authoring-plan-refresh`. Authority: Accepted ADR-0041 and the
maintainer's explicit request to repair the compiler using this compilation's
findings and retained 08-05/08-24 evidence. This is bounded Skill maintenance,
not Package A implementation or Acceptance.

## Historical evidence and revised conclusions

- Commit `1fa82514` retained 08-05 round-7 compiler results, including
  `compiler-result.isolated-1.json` (invalid MCP transport configuration entered
  V3 schema repair) and `compiler-result.openai-api.json` (403 environment error
  reported as schema-repair failure). Environment errors cannot be repaired by
  asking another semantic worker for JSON.
- The 08-05 round-7/recompilation-4/cer-repair-1/current-plan bundle is an OLD
  precursor, not the final accepted 08-05 result. Existing regression tests
  exercise its frozen-production, non-authorable-test and RED-role defects and
  the exact-semantic-projection repair. This supports early consumer checks;
  it does not revoke 08-05 Acceptance.
- Commit `d005b777` retained the 08-24 round-2 repair closure: round-1 used
  Cartesian acceptance bindings. Its 105 semantic edges still required semantic
  review. Quantity/exact cover alone is insufficient; V4 remains necessary.
- The retained current 08-24 bundle has 351 obligations and 73 slices. Its
  structural contract, chain audit and projected execution checks pass here.
  This does not prove that all historical 08-24 failures were V3/V4 compiler
  defects, or constitute a new platform runtime acceptance.
- The existing 08-06 bundle has 286 obligations and 25 slices. Structure, chain
  and projected execution pass. Twenty-four projected slices name absent
  planned production files and receive conservative first-use warnings. These
  are not 24 proven execution failures: predecessor work may create an owner.

Exact paths, hashes and results are in `historical-plan-check.json`. The script
only reads those historical inputs and verifies their bytes remain unchanged.
Hints in that audit are reconstructed from published slices, not claimed as
original worker outputs. Earlier evidence pruning means this is a targeted
sample audit, not a complete historical failure census.

## Repairs

1. Shared ownerless-guard rules at V3, V7 and final validation; ordinary and
   grouped output schemas can express an empty owner list. Only bounded
   test-only governance/constraint guards can pass without production owners.
2. Before V4 Acceptance alignment, project the V3 candidate through the existing
   exact-cover, partition, feasibility, structural and Quick Dev handoff gates.
   Preview is copy-only and records content-addressed non-authorizing diagnostics.
   V1 source recall may precede this check. Final gates still run after V4.
3. Normal, grouped V3, V4 domain and V4 source-gap workers use one transport
   retry policy. Configuration/auth/unknown failures, cancellation and timeout
   stop without schema repair or timeout-driven fan-out. Positive transient
   service errors retain at most three attempts. Prior diagnostics and valid
   exact child caches survive retries/resume.
4. V7 recognizes pytest node file identity. Conditional assertion-failure prose
   is no longer mistaken for an unconditional failing program. Actual RED
   remains the consumer's responsibility.
5. Early planned-production first-use warnings identify the Quick Dev boundary.
   Existing exact semantic-projection handoff repair is reused; no new review
   cache or reviewer framework is introduced.

## Verification

- `final-regression.log`: 275 passed, 15 subtests passed across 14 targeted test
  modules. Includes native public CLI success/failure subprocesses using explicit
  injected fixtures, old 08-05 handoff regression, current path contracts,
  specialized transport stop behavior, and exact-child cache resume.
- `package-validation.log`: all 10 VDD package checks passed.
- `historical-plan-check.log` / `.json`: read-only 08-05/08-06/08-24 cross-checks.
- `git diff --check`: passed for changed delivery paths.

Test modules: test_execution_preflight, test_ch456_v3_execution_contract,
test_ch456_planned_red_feasibility, test_semantic_plan_contract,
test_ch456_semantic_worker_transport, test_ch456_source_role_transport,
test_quick_dev_handoff, test_ch456_v3_inline_context_repair,
test_ch456_v4_atomic_recall_domain, test_ch456_worker_transport_composition,
test_ch456_v3_total_coverage_and_slice_cohesion, test_semantic_compiler_ch456,
test_ch456_live_v3_worker_contract, test_validate_skill_contract.
All live in `.agents/skills/vdd-execution-plan/scripts/tests/` and run with
`python -B -m pytest -q <paths>`. No live provider traffic was used for these
fixtures. No Windows/Godot/.NET runtime acceptance is claimed.

## Remaining boundary

The previously published 08-06 plan-ready state is untouched. Quick Dev's real
first-use RED protocol for new production entries remains to be resolved before
Package A implementation. This repair reports the issue earlier; it does not
seed production in Q2, accept missing-import RED, or change Quick Dev Q4.
Existing source-specific compatibility adapters have not been comprehensively
rewritten. Semantic source gaps still require genuine V4 judgment and bounded
source-bound repair; no claim is made that every V3/V4 failure is eliminated.
