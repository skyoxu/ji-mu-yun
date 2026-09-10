# Explicit Bootstrap And Bounded Closure

Read this guide only for the operation selected in SKILL.md. Commands run from the repository root unless stated otherwise; inline paths retain their original repository/Skill-root meaning.

The following steps continue the orchestration only when Bootstrap was explicitly requested or an existing explicitly selected lineage is being recovered.

5. For an explicitly selected semantic route, publish the immutable Bootstrap
   requirement decision and obtain a fresh repository-owned `inspect-lineage`
   projection, including zero rounds. The default `deterministic_only` route
   does not call Bootstrap and proceeds directly from the receipt-bound
   finalization above. When Bootstrap is explicitly requested, the current
   `decide-bootstrap` command accepts only a repository root, a prepared
   Acceptance run-input reference, a hash-bound deterministic evidence
   reference, and maintainer intent. It replays candidate custody, changed
   paths, the repository-owned semantic trigger policy, and policy hashes
   itself. Caller-authored requirements, profiles, risk booleans, and reason
   codes are legacy-read-only inputs and cannot publish a current decision.
   Incomplete deterministic evidence is `blocked` and cannot be routed to
   Bootstrap.
6. Produce the bounded route with `route-acceptance`, the thin public alias for
   `prepare-bootstrap`:

```text
py -3 .agents/skills/run-refactor-implementation-acceptance/scripts/acceptance_cli.py route-acceptance \
  --request <bootstrap-route-request.json> --out <bootstrap-route.v1.json>
```

7. Before starting a semantic run, attempt `import-bootstrap` only with an
   explicitly selected finalized run and the exact prepared input and route.
8. Follow the route's typed `nextAction`. Invoke `run-phase-bootstrap-review`
   for `full_implementation_conformance` or `focused_repair_verification`, but stop
   for its explicit high-cost acknowledgement before any model process starts.
    If the route publishes `findingModeReentry=user_confirmation_required`, first
    show the typed trigger, expected benefit/cost, your recommendation, and a
    confidence in `[0,1]`; obtain explicit user confirmation and create the
    Bootstrap CLI re-entry authorization before prepare. The recommendation is
    advisory: explicit confirmation may proceed after either `recommend` or
    `do_not_recommend`.
    When the user explicitly declines that later discovery proposal, do not
    launch Bootstrap. If repair completeness passed, no novel P0/P1 exists,
    the consumed-round count is exactly one, and the only typed trigger is a
    repair-caused authority/context or high-risk-boundary change, run
    `decline-review-reentry`. The append-only result records maintainer risk
    acceptance and may publish `acceptance-passed`; it never authorizes commit,
    release, or archive. Any novel P0/P1, missing replay, stale binding, or
    different round fails closed.
9. Import the finalized Bootstrap result, then continue finding mapping,
   impact projection, evaluation, finalization, and package validation.

Treat `review-history-index.v1.json` and cost-calibration candidates as
non-authorizing observations only. They may explain expected cost and semantic
yield but must never enter a `route-acceptance` request, change `routeKind`,
create `clean`, or satisfy exact reuse. A promoted Bootstrap calibration is
consumed by the Bootstrap producer under its own binding.

For P2-only output, dispose findings in the current semantic run and use
targeted deterministic closure. New runs prefer the exact-set P2 v2 bundle;
stored v1 chains remain read-only compatible. For P0/P1 repair, require the
Quick Dev handoff and `audit-repair-completeness` before routing the next
bounded action. A complete Round 1 repair without an escalation trigger routes
to exactly one independent focused repair verifier. Never open a complete
review without its typed trigger and never create Round 4.

Treat the Acceptance route's maintenance and finding fields as first-class
control data: `maintenanceMode=ai-native-single-maintainer`; multi-maintainer
concurrency and external requirement-injection findings shift P0 to P1, P1 to
non-blocking P2, and P2 to ignored. Round 1 discovery is automatic. Later
discovery is only a proposal until the Bootstrap CLI validates the typed route,
recommendation, confidence, and explicit user confirmation.

When the current lineage has consumed three rounds and routes to
`manual_pause`, do not treat the pause as acceptance or create a successor to
reset the budget. A repaired target may use the ADR-0054 two-stage deterministic
closure lane:

1. Repair every confirmed Round 3 finding and produce a current Quick Dev
   handoff, controlled receipts, targeted tests, validation references, and a
   reproducible repair-completeness projection with
   `semanticRoundsConsumed=3` and the Round 3 run as predecessor.
2. Run `prepare-manual-pause-closure` with the current manual-pause route and
   the hash-bound `prepare-bootstrap` request that produced it, the
   blocked finalized v3 envelope from the current implementation-conformance
   or adopted upstream-plan lineage, exact finding-to-repair mappings, and the
   current protocol authorities and a finalized clean/advisory protocol-review
   envelope. The review must use `bootstrap-skill-route`, and its frozen
   artifact set must byte-bind the current protocol implementation, schemas,
   Bootstrap Skill and producer, public Acceptance CLI, review-cycle policy,
   Skill, ADR, and standard. It must canonically replay the complete
   finalized run and reject every remaining `unverified` verifier decision;
   selected envelope fields and maintainer judgement cannot replace either
   check. If that protocol review itself exhausted a blocked Round 3, the
   consumer may instead accept the exact composite authority emitted by one
   CLI-authorized `bootstrap-focused-repair-verification` at the same Round 3.
   That lane binds the blocked envelope, exact finding set, current
   deterministic repair closure, explicit user confirmation, and a passed
   verification-only focused envelope; it cannot create Round 4, findings,
   escalation, or `acceptance-passed`. The challenge carries `authorizes=[]`.
   This composite replays the focused envelope and authority from current bytes,
   but validates the authority-bound blocked predecessor as a frozen eligible
   envelope; it must not revalidate that predecessor's old repair closure
   against the newer protocol bytes that the focused verifier already covered.
   Replay the Bootstrap producer from the request repository's own Skill path;
   a caller-adjacent producer or a missing repository-owned producer fails closed.
3. Stop for an explicit maintainer acknowledgement bound to the challenge hash
   and exact confirmed finding IDs.
4. Run `finalize-manual-pause-closure`. It hashes the same challenge byte
   snapshot that it validates and recomputes every binding;
   only its final closure result may publish `acceptance-passed`.

Each finding mapping must select a composition receipt whose bound producer or
consumer paths cover that finding's changed paths and whose registered command
names its mapped targeted tests. Repair completeness reruns every registered
composition command through the controlled runner and rejects saved stdout or
stable execution fields that do not match the current replay. Producer and
consumer path sets are disjoint, and a read-only controlled command must leave
the repository byte manifest unchanged even when a touched file was already
dirty before execution. Tracked deletions use stable tombstones. Closure
request paths are repository-relative after resolved-root normalization, and
finding-repair mappings are canonicalized by finding ID.

This lane never launches a model, reopens the target Bootstrap lineage, creates Round 4, changes a
verifier decision, or authorizes commit, release, or archive. Independently
validate and review a new closure-protocol revision before using that revision
to close a real target; the protocol cannot approve itself.

## Bootstrap Routing

Bootstrap is explicit-only. Decision v11 retains risk classifications as
context, but only `maintainerIntent=request` can require a review. A control
plane or high-risk path alone never requires or launches Bootstrap. Incomplete
Acceptance evidence remains blocked; Bootstrap cannot substitute for it.


When the immutable Bootstrap requirement decision is `required`, deterministic
validation must publish an append-only route through `prepare-bootstrap`. The
route freezes the consumer-side decision, capability binding, Bootstrap-owned
launch sidecar, stable target-derived `lineageFamilyId`, consumed-round view,
and optional repair-completeness result. It selects exactly one route kind:
`deterministic_only`, `focused_repair_verification`,
`full_implementation_conformance`, or `manual_pause`.

For every required Bootstrap route, pass `repository_root` and obtain a fresh
hash-bound `inspect-lineage` projection, including the zero-round initial state. Omitting
the projection fails closed; absence is never interpreted as a fresh budget.
`prepare-bootstrap` replays that projection itself. A repair route must also
carry its original repair-completeness request so the result can be reproduced
from current repository bytes.

When a repair route has already consumed at least one semantic round and
selects `focused_repair_verification` or `full_implementation_conformance`, pass the
saved route to Bootstrap as `--acceptance-repair-route` and its replayed
completeness projection as `--acceptance-repair-completeness`. Bootstrap
revalidates their byte, family, round, and typed-entry bindings. For the initial
Round 1 `full_implementation_conformance` route, do not pass either repair
argument; retain that route only for the later Acceptance import binding. Pass
the current append-only prepared Acceptance input to Bootstrap as
`--acceptance-run-input`. Candidate tombstones may then remain in `--scope` and
context classes: Bootstrap replays custody and identity, requires current
absence, and freezes old bytes only from the bound immutable Git baseline.

The deterministic CLI never launches an LLM process. The Skill orchestrator
must invoke `run-phase-bootstrap-review` when the selected route requires it,
then complete Bootstrap preflight, identity-equivalent access probe, and
explicit high-cost launch authorization before any reviewer layer starts. It
must not merely report that review is required and stop. A deterministic pass
without a required finalized Bootstrap envelope remains a non-authorizing
candidate, not an implementation-acceptance pass.

After a focused repair run finalizes, call `import-focused-repair` with the
repository-relative `focusedRun` directory plus the exact Acceptance route and
repair-completeness path/hash references. The command canonically replays the
Bootstrap producer; never accept a caller-supplied focused envelope.

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
conformance. After the first P0/P1 repair, the default route is a single
focused repair verification only when no new P0/P1, authority/context graph
change, or high-risk boundary change exists. Any such trigger selects complete
three-layer review as a non-authorizing proposal requiring recommendation,
confidence, and explicit user confirmation. A clean focused result closes the
ordinary repair; a focused blocker routes back to repair, and the focused
verifier cannot report a new trigger. After two consumed complete rounds, a complete repair with no
typed trigger routes to deterministic closure. Three consumed rounds route to
`manual_pause`.

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
