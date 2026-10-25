# VDD public interrupted-source recovery repair

## Approved step and stop point

Approval: Sentinel_1d028fb3a0208191bc1f636ed10b693e (2026-10-24 18:04 UTC).
This step repairs and tests public recovery only. The original r3 compilation was NOT resumed. No real model, BMAD skill, reviewer, A/B, business query, implementation, Acceptance, push/PR or CI action ran. All public compiler executions below used disposable /tmp repositories with a deterministic fake author and fake advisory adapter. The native CLI, patch stack, host request/response consumer, caches, receipts and publication gates were real repository code.

## Root cause and reviewed minimal design

The public CLI adds prepared advisory query context to each worker input and prompt. Repair changes stage/operation, timestamp/request/episode and Git provenance, so raw transport cache keys changed despite unchanged requirement semantics. r3 also lacks canonical plan-ready state; --resume-from cannot restore a V2 instruction pointer. Treating old V2 progress or a response file as accepted state would be unsafe.

The minimal fix is V1 source-content candidate replay, not state import or an extra planning chain. Identity binds the actual source section/ref, supplied interpretation context, extraction prompt and source-role policy. Query-run advisory JSON and source position/whole-file provenance are excluded from *extraction* identity because V1 is instructed to extract only frozen source semantics; V0 still verifies current actual file bytes. A changed section/context/policy invalidates its extraction; an unchanged sibling section or Git-only commit does not. Actual full-domain source checks keep their existing complete-source/candidate dependencies and native validation.

New normal transport results store non-authorizing candidate metadata under .compiler-cache/source-replay. They remain raw candidates, not saved V2 or completion judgments. Cache tampering blocks; current schema, source binding, V2 and downstream checks still run on replay. No fixture result is promoted into this content cache.

For older caller-session caches, the optional public --resume-worker-session selects one explicit original repository/output-bound transcript. It requires the exact returned host request/result/response binding, native output, correctly addressed raw cache and schema-valid native receipt, all with matching hashes and current normalized semantics. Ambiguous/corrupt matching evidence blocks without requesting a replacement model. Timeout/cancel/missing-result/unconsumed answers are not adopted. Legacy lookup writes no old cache, receipt or state. Current permission/query refusal still precedes all worker replay.

## Changed files

Seven files; changed-files.json and STEP-DELTA.patch isolate this step from the earlier timeout/query changes. before/ contains reconstructed previous-step bytes verified against the previous step's frozen hashes.

- scripts/vdd/compile_plan.py: validated --resume-worker-session option, scoped recovery configuration and diagnostic replay counts.
- .agents/skills/vdd-execution-plan/scripts/semantic_resume_cache.py: bounded source identity/candidate cache and original native host-witness verification.
- .agents/skills/vdd-execution-plan/scripts/semantic_worker_transport_patch.py: replay at the existing transport seam, retaining all current native validators.
- .agents/skills/vdd-execution-plan/scripts/tests/test_public_source_cache_resume.py: public CLI/host protocol fixture and positive/negative controls.
- VDD SKILL.md and references/planning-operation.md: exact supported route, evidence restrictions, V0/V2 recheck and continuation boundary.
- docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md: user-approved bounded cache-recovery decision.

No Quick Dev, business implementation, approved input/contract or original failure history was edited in this step. The preceding 1800-total/600-inactivity unit supervisor and bounded retries are unchanged.

## Public entry evidence and tests

public-final.log: 11 passed in 8.79 seconds. public-fixture-summary.json and fixture-native-results/ retain compact raw native results selected by exact copied entry content, not latest-success selection.

1. Interrupt the real public CLI via native host cancellation at V3. Preserve its accepted V1/source-check cache and original transcript. Remove only new metadata in this disposable fixture to model the older r3 format. Resume using the public option and a fresh live host session: plan-ready, zero new V1/source-check requests, one V3 and one Acceptance-alignment request. The old transcript is byte-identical. legacy_v1_replays is 2 in this one-anchor fixture because the canonical compiler internally validates/replays V1 again later; counters count lookups, not unique sources or model calls.
2. Two-anchor fixture: edit only FR-1. Public resume requests exactly FR-1 extraction, reuses FR-2 and recomputes the genuinely changed full-domain source check. A later Git-only commit requests no V1/source-check work.
3. Corrupt receipt, cache candidate or response binding: public recovery blocks with artifact-integrity and zero new worker requests.
4. Old timeout or unconsumed response: no legacy adoption; a fresh V1 request is required. A file's existence never supplies authority.
5. Current advisory/security refusal blocks before replay, despite usable cache. This tests ordering with a deterministic adapter, not real Locator permission behavior.
6. V1 candidate reuse still invokes the current V2 guard (two actual V2 returns across two invocations) and the later dependency preflight. An unresolved dependency still returns repair-vdd at V3-execution-preflight; no canonical state is published. V2 is not incorrectly claimed to own this later dependency check.
7. Content/context/source-role differences and content-cache tamper controls are covered independently.

regression.log:22 passed (transport, role guidance, failed-resume and full patch-stack composition). package.log:22 passed plus15 subtests; skill-validation.json:ok/no findings. budget.log:12 passed, including per-unit cumulative retry, silence, genuine progress, aggregate >1800 across healthy units, cancellation/SIGTERM and owned process-tree cleanup.

Earlier diagnostic attempts are retained: first-test.log contains a duplicate cancellation in the new fixture driver, fixed by servicing each request once. public-tests.log contains a wrong test assumption that dependency-target validation belonged to V2; source inspection identified its actual V3 execution-preflight owner, and the test now asserts both genuine V2 revalidation and that owning guard. No production gate was weakened for either test correction.

## r3 eligibility without recovery

r3-eligibility.json records a read-only compatibility-witness check: 61 distinct V1 source caches qualify; none rejected. It did not run current V0/V2/query gates, compile, invoke a model, create source-replay metadata or accept a new contract. Original r3 output plus original host transcript tree digest remained exactly:

47dedc5c6ab0dbd84497f52a247e7756dab00b6895d3ee26642abb08bfe61672

Previous inspection already established the four native resolved source-check envelopes cover all 305 IDs without gaps/inventions and have matching result hashes. They remain eligible only if replay produces the same current domain and the native resolved-recall validators accept them. The public fixture proves this unchanged-domain reuse route; a real r3 run has not been executed to claim actual hits.

V2's prior returned log is not imported as success. Current V0 source integrity and V2 structural checks run again cheaply. Missing dependencies still belong to their later execution guard. V3 has ZERO accepted contracts: all 305 contracts remain unfinished. Four 600-second timed-out requests and one late/unconsumed response are diagnostic/authoring history, never accepted cache. At the current maximum four obligations per initial batch, at least77 initial contract batches may be needed, plus genuine validation/repair and V4/downstream work. Do not imply that only four/five requests remain. Existing V3 cache rules were not redesigned in this bounded V1/public-entry repair.

## Suggested next public command (NOT EXECUTED)

Create one fresh caller session explicitly, keeping the original r3 session read-only. The exact proposed commands are in NEXT-COMMANDS.txt. Use the same seven frozen inputs, original r3 out-dir and self-hosted plan profile; add --resume-from first-failed-stage and --resume-worker-session logs/vdd-scoped-compile-20261024-host-r3. Use the current native public unit supervisor, NOT the old per-run aggregate watchdog.

The command will refresh the current query/security gate, replay eligible V1/source checks with current validation, then continue V3/V4/all remaining native publication gates. It is not a V3-only stop or a guarantee of readiness. Actual future cache hits/new requests must be reported from that execution. Do not clear budget ledgers or relabel old timeout results.

## Limits and next decision

Linux fixtures and short processes only; no Windows execution, original long compile, original long consumer tests or independent stage review. Prior unrelated root-temp fixture and selective-cache failures remain outside this step and were not represented as fixed. No model/skill model configuration changed.

No implementation/protocol expansion blocker remains for this bounded route. Current real policy/input checks and unimplemented V3 contracts remain to be evaluated only after the user authorizes a real recovery. This step is stopped pending that confirmation.
