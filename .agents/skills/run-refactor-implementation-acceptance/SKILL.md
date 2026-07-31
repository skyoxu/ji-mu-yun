---
name: run-refactor-implementation-acceptance
description: Build deterministic implementation-acceptance evidence for one explicit refactor plan.
---

# Refactor Implementation Acceptance

This Skill builds deterministic implementation-acceptance evidence for exactly one explicit target plan. It does not implement target code, run Bootstrap automatically, approve a review, commit, hand off, release, or deploy.

## Modes

- `evidence_only` is the default. It reads current manifests and evidence and may only produce non-authorizing candidate conclusions.
- `controlled_validation` is available only after the caller supplies typed commands and isolated write roots. It cannot write target production code, live Phase state, workspaces, or historical evidence.

## Bootstrap Routing

When the immutable Bootstrap requirement decision is `required`, deterministic
validation must publish an append-only route through `prepare-bootstrap`. The
route freezes the consumer-side decision, capability binding, Bootstrap-owned
launch sidecar, stable target-derived `lineageFamilyId`, consumed-round view,
and optional repair-completeness result. It selects exactly one route kind:
`deterministic_only`, `focused_repair_review`,
`full_implementation_conformance`, or `manual_pause`.

For every required Bootstrap route, pass `repository_root` and obtain a fresh
hash-bound `inspect-lineage` projection, including the zero-round initial state. Omitting
the projection fails closed; absence is never interpreted as a fresh budget.
`prepare-bootstrap` replays that projection itself. A repair route must also
carry its original repair-completeness request so the result can be reproduced
from current repository bytes.

When the route selects `focused_repair_review` or
`full_implementation_conformance`, pass the saved route to Bootstrap as
`--acceptance-repair-route` and its replayed completeness projection as
`--acceptance-repair-completeness`. Bootstrap revalidates their byte, family,
round, and typed-entry bindings. Do not pass deleted paths as live `--scope`
arguments; Bootstrap recovers their old bytes from predecessor evidence.

The deterministic CLI never launches an LLM process. The Skill orchestrator
must invoke `run-phase-bootstrap-review` when the selected route requires it,
then complete Bootstrap preflight, identity-equivalent access probe, and
explicit high-cost launch authorization before any reviewer layer starts. It
must not merely report that review is required and stop. A deterministic pass
without a required finalized Bootstrap envelope remains a non-authorizing
candidate, not an implementation-acceptance pass.

Before starting a new semantic run, the caller may invoke `import-bootstrap`
with one explicit finalized run, the append-only `prepare-run` output, and the
exact append-only `prepare-bootstrap` route that launched that run. The command
revalidates the current candidate manifest, changed paths, custody, frozen
knowledge context and accepted knowledge sources, reruns Bootstrap
`validate-finalized-run`, and requires every file in the route's complete
seven-class `reviewScope` to be present in the run's frozen artifact binding.
The prepared Acceptance input, candidate manifest, and knowledge artifacts
must also match their frozen artifact entries. The v3 import envelope directly
binds the route's file hash and canonical document hash; Round 1 does not
pretend the route was a repair-route artifact. Every candidate changed path
must be in the route's `changed-production-code` class.

Exact reuse is emitted only as `bootstrap-import-envelope.v3`. It requires a
non-null exact `candidateBindingHash`, current profile/policy/authority, the
`bootstrap-implementation-conformance` profile, a complete finalized v3
validation envelope, `clean` final status, and a
`full_implementation_conformance` or `focused_repair_review` route. The route's
lineage state must be the immediate predecessor of the selected finalized run,
and that run must be the current reconstructed lineage head. Historical import
envelope v2 evidence remains readable under its original v1/v2 finalized-run
contract but never grants exact reuse. The import binds the canonical
repository-relative Bootstrap run directory and requires the Acceptance
Auditor attestation to match the finalized review/input identity. Any drift
rejects the import and leaves the existing bounded review route unchanged. This is
deterministic validation reuse, not LLM-output caching; historical cost or
finding baselines cannot authorize it.

For a required review, `prepare-bootstrap` must build a
`minimal-complete-closure` from explicit repository-relative files in all
seven implementation-conformance classes: implementation plan, changed
production code, directly affected consumers, tests and acceptance, current
runtime or acceptance evidence, repository rules, and referenced standards.
Do not pass a whole Skill, source, test, document, log, or execution-plan
directory merely because it contains one relevant file. The generated
`reviewScope` is the exact input for Bootstrap `--scope` and `--context-class`
arguments; Bootstrap still owns snapshotting and launch authorization.

A malformed child JSON response, invalid Artifact View receipt, or failed
Codex process is a transport attempt failure. Retry the same role in the same
Bootstrap run after inspecting the attempt evidence; it does not consume a
semantic round or require a successor lineage. P2-only results are disposed in
the current run and use deterministic targeted closure. They do not trigger a
new complete semantic review. The original target plan remains the acceptance
target unless an explicit supersede or incompatible-scope decision exists.

The lineage family is derived from the original `execution-plans/<target>`
root. In-place repairs and successor history for that target retain it; a new
`changeId` does not reset the review budget. Round 1 uses full implementation
conformance. After the first P0/P1 repair, the default route is a focused
repair-delta review. After two consumed rounds, a complete repair with no new
P0/P1, authority/context graph change, or high-risk boundary change routes to
deterministic closure. Only those typed triggers may open Round 3. Three
consumed rounds route to `manual_pause`.

Before any repair re-entry, require Quick Dev's standard handoff and run
`audit-repair-completeness`. The audit discovers sibling callsites from the
declared roots, requires each match to be changed or explicitly excluded, and
validates successful controlled producer/consumer composition receipts whose
input bindings cover every producer and consumer. It derives the exact changed
set from a hash-bound complete candidate manifest and binds present changed
files by content hash, deleted files by their baseline hash, direct consumers,
targeted tests, and validation references. Each
composition check must cover a changed path, use declared direct consumers,
and expose its receipt as a validation reference. Before routing, require all
changed paths, inventory matches, composition bindings, command registries,
receipts, consumers, tests, and validation references to be members of the
same hash-bound `minimal-complete-closure`; consumers and tests must also be in
their corresponding context classes. The audit and route carry `authorizes=[]`;
the plan-local final predicate still decides implementation acceptance.

## Current Core

Before `prepare-run`, create one Refactor Acceptance-owned knowledge context
through the canonical Locator:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/prepare_knowledge_context.py \
  --repository-root <repo> --request-id <id> --query <query> \
  --required-module acceptance-scope \
  --accept <candidate-path>=acceptance-scope \
  --output <target-plan>/knowledge-context.refactor-acceptance.v1.json
```

The adapter uses `consumer=refactor-acceptance`, records one accepted or
rejected decision for every Locator candidate after reread/hash verification,
and fails closed on publication, snapshot, policy, projection, request/result,
or read-set drift. It never uses unpublished staging inputs.

The formal CLI requires that frozen file at the `acceptance-run-input` freeze
point:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py prepare-run \
  --input <request.json> --knowledge-context <target-root-relative-path> \
  --out <run-input.json>
```

Historical function-level inputs without a knowledge context remain readable;
new CLI preparations cannot omit it. Later phases consume the frozen summary
and never issue another Locator query. The shared context validator must
byte-match current main, and the complete Locator read-set is revalidated
against both its source commit and current worktree before the summary freezes.

`scripts/acceptance_cli.py prepare-run` validates a hash-bound run input with replayable baseline and candidate content manifests, then writes a new non-authorizing run-input artifact. Commit candidates are checked against raw bytes from resolved immutable Git commits, and the resolved baseline/candidate OIDs are persisted in `candidateCustody`. Dirty-worktree and proposed-commit-set candidates must declare `candidate_frozen_snapshot_path` as `.acceptance-snapshots/<run_id>` beneath the target root; symlinks and live workspace substitutes are rejected, and the snapshot manifest receipt is persisted. `policies/phase-service-code-review.v1.json` is the Phase-only policy pack. Pure Godot inputs are rejected as an unsupported code-review domain; mixed candidates must retain an unreviewed external partition.

`analyze-diff-coverage` consumes a frozen `phase-changed-line-set.v1` and a current Cobertura report. It uses only added or modified executable `PhaseA.Platform/**/*.cs` lines for the denominator, records every exclusion reason, and returns `incomplete` when a source mapping is missing. It never substitutes repository-wide coverage.

`audit-task-checklist` reads only explicitly declared authority checklist files. A checked item is `verified` only when its stable item identity has current matrix, implementation, test, and evidence references; source hash drift, checkbox-only closure, and request-controlled optionality fail the result. `run-command` resolves an exact descriptor from a hash-bound command registry; it never executes a caller-supplied descriptor. `run-phase-scan` is available only in `controlled_validation`, executes that registered shell-free command from a hash-verified frozen candidate snapshot, and requires its declared Phase read scope to exactly cover the candidate's Phase changed paths.

`audit-repair-completeness` consumes the append-only Quick Dev handoff without
translation. It revalidates the baseline/candidate manifests and rejects an
omitted or invented changed path. Every inventory is discovered from current repository bytes and
every composition check must reference a successful controlled-command
receipt. Feed its result and the Bootstrap `inspect-lineage` projection into
`prepare-bootstrap`; do not hand-author consumed rounds or route kinds.

The matrix, conditional Bootstrap import, action recovery, and final authorization stages are implemented only when their own plan slices and predicates are complete. A passing unit test or a Bootstrap `clean` result is not Program DoD.
