# Lifecycle State Contract

The static machine-readable owner is [lifecycle-state-contract.json](lifecycle-state-contract.json). Every new plan uses:

`draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`

VDD owns `draft` and `plan-ready`. Before `plan-ready`, new Chapter 4/5/6 plans must pass `scripts/semantic_plan_contract.py`: V5 emits only pre-slice semantic cover, V6 partitions behavior slices, and V6A binds the final many-to-many cover with exact ordered `stage_scope=[red, green, refactor, terminal]`. The VDD bundle must contain no run IDs, receipts, observations, runtime-edge hashes, current-snapshot hashes, process outcomes, or other future execution facts.

`agent-context.json` is a deterministic projection of the validated plan, not a second source of truth. Its obligation/Acceptance/selector sets must project the owning slice exactly.

The maintainer may explicitly publish `implementation-authorized` when that governance capability is enabled; it is not a development truth-floor prerequisite. Bootstrap Review is optional supplemental evidence and cannot publish a lifecycle state. Quick Dev may publish only `implementation-complete`, after terminal full validation. The implementation acceptance Skill owns `acceptance-passed`; the archive Skill owns `archived`.

Old state names and old v1 evidence shapes are accepted only by compatibility adapters for repair or replay and are never emitted as current authority. No transition implies a later transition. An authorization override never implies acceptance, handoff, release, or archive.

## Observed Behavior Routing Capability

For bundles with `vdd.behavior-routing-intent.v1`, the original four-stage
`stage_scope` records the possible missing-behavior path. Quick Dev derives the
actual required path from current controlled probe evidence: missing uses
RED/GREEN/REFACTOR plus terminal, present uses regression plus terminal. This
runtime projection retains every current obligation and is re-derived at Q7/Q8;
VDD never writes runtime disposition, observation or success into its plan.
Bundles without the capability keep the original mandatory four-stage path.
