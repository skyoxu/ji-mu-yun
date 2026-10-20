# Online route and Package A VDD repair

Base branch commit: `271b43783d446aa541d9fe2218f44a2ba6629833`.
User authorization: add an online route to VDD, Quick Dev TDD and Acceptance;
continue VDD repair. Package A production implementation is not part of this work.

## Changes

- Added shared host-session transport and a thin wrapper around the three native
  entries. Exact request/session/hash binding, finite timeout, cancellation and
  one-shot response checks preserve native consumer authority. CLI/API defaults
  remain available. No separate-model reviewer identity is claimed.
- Removed the irrelevant Codex model-config prerequisite from deterministic
  Acceptance no-launch decisions. Optional child recovery retains its policy.
- VDD cancellation/timeout stops the host attempt instead of starting repeated
  transport/schema repair requests.
- Normalized declared pytest node snapshots to actual declared files; retained
  node selectors. Handoff parsing recognizes Python's `-B` option.
- Preserved exact rejected V7 candidate diagnostics for bounded authoring repair.
- Made pure test-only governance guards consistent across partitioning, V7 and
  final routing. Empty owner does not permit production writes, behavior RED or
  product behavior; those still fail. No test is promoted into a production owner.
- Repaired Package A contracts through source-bound candidate input: missing
  cancellation ownership; 17 wrong or incomplete oracles; 11 conditional failure
  phrases; 22 out-of-scope execution bindings; conflicting forbidden/snapshot
  declarations. Current production owners are limited to Package A artifacts.

## Actual results

`compiler-result-09.json`: native `plan-ready`, all 286 source obligations and
Acceptances covered, 297 V5/V6A edges, 25 slices, zero invented/source-gap claims.
V4 was performed as a distinct semantic review task by the online caller; this
is not a claim of a separate model/process independent reviewer.

Verification under `logs/08-06-online-plan-repair/`:

- `route-regression-final.log`: 166 passed, 21 subtests passed.
- `package-regression.log`: 41 passed, 24 subtests passed; includes ownerless-guard
  negative cases and the three Skill package contract tests.
- `vdd-package-check.json`: 10 checks, no findings.
- `acceptance-package-check.json`: pass, no findings.
- `model-routing-isolated-regression.log`: 16 passed, 3 subtests passed with an
  explicit unit-only model-ID fixture; no real child launch/provider call.
  The unconfigured whole-suite attempt is retained separately and failed on the
  existing local model-config requirement for child routes. This is not a CLI
  integration test and is not presented as one.
- Real Quick Dev authoring transport fixtures exercised permitted test edits and
  rejected an undeclared production write. They are not Package A execution.

The interrupted fifth compiler attempt left an expired unanswered host request;
it was not reused or fabricated into a result. A new native invocation reached
publication. Earlier failure outputs remain diagnostics, never readiness authority.

## Limits

No Package A tests, validator or standard were implemented. No Windows/Godot/.NET
runtime behavior, complete Quick Dev lifecycle, Q8 or Acceptance was certified.
The new-production first-use blocker in LOCAL-HANDOFF remains before Q2/probe.
The source requirements did not change in this repair. Existing historical
requirements, receipts and semantic evidence were not rewritten as successes.
