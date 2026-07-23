# Pre-writing Clarification Gate

## Contents

1. Purpose and borrowed BMad mechanisms
2. Read-only discovery
3. Boundary dimensions
4. Question rounds
5. Confidence and exit
6. Persistence and recovery
7. State commands
8. Create and repair behavior
9. Headless and stale-state handling
10. Write boundary

## Purpose and borrowed BMad mechanisms

Use this gate before a create or repair operation writes a VDD execution plan. The gate combines established BMad interaction patterns without changing BMad/GDS Skills:

- Product Brief and PRD: invite the complete brain dump, ask what was omitted, and narrow from broad context to specific gaps.
- Forge Idea: challenge vague terms, boundaries, and assumptions in dependency order.
- Quick Dev: use stable numbered questions, verify every answer, and re-ask only unresolved items.
- Advanced Elicitation: loop until the user explicitly chooses to proceed; never let the model silently end the loop.

Do not inherit PRD Fast path or Spec express behavior. Assumptions and open questions may remain visible, but they cannot bypass clarification or authorize `plan-ready`.

## Read-only discovery

Select create or repair first. Then read repository instructions, approved intent sources, current-state authority, standards and ADR indexes, protected paths, relevant callers, the existing target, and current validator output. Find repository facts directly rather than asking the user.

Before exit, the only permitted writes are clarification state and read-only investigation evidence outside the target plan. Do not modify plan Markdown, schemas, fixtures, validators, tests, source code, generated history, or implementation artifacts.

## Boundary dimensions

Assess five dimensions, each worth 20 confidence points:

1. Goal, scope, and non-goals.
2. Authority sources and current state.
3. Constraints, compatibility, and protected boundaries.
4. Acceptance, failure modes, and evidence.
5. Dependencies, risks, recovery, and evolution.

For create mode, cover the full set when applicable. For repair mode, inherit confirmed authority and ask only about the change signal, baseline defect, delta, affected consumers, preserved behavior, regression acceptance, and stop conditions. Mark a dimension `not_applicable` only with a reason.

Distinguish current implementation differences from authority conflicts. A desired change from current behavior is a delta. Conflicting normative sources, protected rules, or user directions require an explicit user decision and, when necessary, an upstream ADR or standard change.

## Question rounds

Before each round, summarize confirmed boundaries, non-goals, conflicts, open items, and blockers. Ask at least five unresolved questions from the highest remaining dependency level and give a concrete recommendation for each. Use stable run-scoped IDs such as `CQ-001`; retain the ID when re-asking, deferring, superseding, or reopening a question. Every newly recorded CQ must classify its primary uncertainty as `fact_gap`, `user_decision`, or `authority_conflict`; a dependency may point only to an already answered CQ. Once recorded, a stable ID cannot redefine its summary, recommendation, basis, blocking classification, or primary classification. `record-round` may apply only the declared status-transition matrix; reopening settled authority requires `invalidate` followed by the explicit `reopen` command.

Ask fewer than five only when fewer substantive same-level questions exist. Record `same_level_exhausted: true` and a concrete reason. Zero questions is valid when the boundary is complete; do not invent questions to satisfy a quota.

The user may answer `unknown` or defer a decision. Classify it as blocking or non-blocking and record an owner and recheck condition when deferred. Re-ask only unanswered or newly affected questions. Do not reopen settled authority without a new conflict or change signal.

When a round resolves an ambiguous term, record a term candidate with its candidate ID, source CQ, definition, scope, and replaced terms. When a real tradeoff suggests an ADR, record only a decision candidate with its source CQ, irreversible and context-sensitive determinations, tradeoff, evidence references, repository ADR requirement, and disposition. Candidate records are recovery inputs, not authority documents; they must not create or modify a formal ADR during clarification.

End each round with:

- confirmed boundary changes;
- open and blocking items;
- the confidence score and deductions;
- whether the model recommends ending clarification.

## Confidence and exit

Score only from evidence in the five dimensions. Any blocker caps confidence at 89. Recommend ending clarification only at 90 or higher, with no blockers and every applicable dimension grounded.

The model cannot exit. Writing begins only after a real post-summary user turn explicitly states both:

1. no further clarification is needed; and
2. writing may begin.

Generic agreement (`agree`), `continue`, `start`, urgency, high confidence, an initial prompt that pre-authorizes writing, or an LLM/caller-generated statement is insufficient. Equivalent explicit wording in the user's language is valid; do not require one literal sentence.

If the user explicitly exits while blockers remain, record the exit but set `draft_only: true`. The plan may be written only as `draft`; the exit does not resolve blockers or authorize any higher state.

## Persistence and recovery

Use `scripts/clarification_state.py`. Resolve the repository evidence root from local instructions; otherwise use `<project-root>/logs`. The evidence root and target plan must be fully disjoint: neither may equal, contain, or be contained by the other. Reject an overlapping configuration before creating any evidence or target content. Store each run at `vdd-clarifications/<target-slug>/<run-id>/` with:

- `state.json` as the current resumable snapshot;
- `events.jsonl` as append-only lineage with a monotonic sequence, unique event ID, predecessor event hash, canonical payload hash, transition ID, user-turn identity, and authority/target hashes;
- `snapshots/<sequence>.json` as immutable, versioned recovery checkpoints.

Store only minimized summaries, stable IDs, hashes, statuses, confidence evidence, and exit attestation. Never store secrets, tokens, credentials, personal data, or the full conversation. The script rejects sensitive field names plus common bearer, OpenAI, GitHub, AWS, Google, Slack, and private-key value formats. This is a fail-closed minimization control, not permission to persist credentials in other formats. Question objects use a closed field allowlist; camelCase token keys, raw user text or conversation fields, and personal-data keys are rejected rather than persisted.

Only one run may be active for a target. On Windows, target identity is case-insensitive, including a not-yet-created target. Every mutating command is serialized by one cross-process lock scoped to that canonical target identity; the active-run scan and new-state creation occur inside the same lock. Resume the active run by default. A user-directed restart marks an `active`, `closed`, or `invalidated` run `superseded` and creates a successor; never merge histories implicitly. A `superseded` run is terminal and cannot be invalidated, reopened, or superseded again. Before `reopen` activates an invalidated run, it must fail closed if any sibling run for the target is already active. The active-run registry and lock are repository-canonical and independent of the caller-selected evidence root, so concurrent local Codex sessions cannot create two active runs for one target. The registry anchors each run's committed sequence, event head, and snapshot hash, so complete event/snapshot-tail rollback fails closed. State/event mutations use a recoverable pending transition with an idempotent transition ID; a reused ID with different canonical payload fails before an event append.

## State commands

Invoke the helper from the Skill root and keep payload files inside the clarification run or another temporary evidence location, never inside the target plan:

```text
py -3 scripts/clarification_state.py init --project-root <root> --target <target> --mode <create|repair> --interaction-mode <interactive|headless> --authority-hash <sha256:...> --target-hash <sha256:...>
py -3 scripts/clarification_state.py record-round --state <state.json> --round-file <round.json>
py -3 scripts/clarification_state.py close --state <state.json> --exit-file <exit.json>
py -3 scripts/clarification_state.py invalidate --state <state.json> --reason <reason> --current-authority-hash <sha256:...> --current-target-hash <sha256:...>
py -3 scripts/clarification_state.py reopen --state <state.json> --question-id <CQ-NNN> --reason <reason>
py -3 scripts/clarification_state.py supersede --state <state.json> --successor-run-id <run-id>
py -3 scripts/clarification_state.py restart --state <state.json> --successor-run-id <run-id> --transition-id <stable-id>
py -3 scripts/clarification_state.py quarantine --state <state.json> --incident-id <stable-id> --reason <minimized-reason>
py -3 scripts/clarification_state.py validate --state <state.json>
py -3 scripts/clarification_state.py status --state <state.json>
```

Use `scripts/fixtures/clarification-state-pass.json` as the state shape example. A round payload supplies question objects, five dimension scores/evidence entries, `recommend_exit`, confidence analysis, and boundary updates. An exit payload supplies current hashes and the minimized user attestation. Never place raw user text or secrets in either payload.

## Create and repair behavior

Create mode performs full boundary discovery but asks only genuine gaps after read-only investigation. Even a complete initial request requires a post-summary user exit turn.

Repair mode preserves existing authority, inventories the complete target, and limits questions to the proposed delta and its blast radius. Do not repeatedly ask the user to reconfirm facts already established by current authoritative artifacts.

Pure read-only review does not trigger this write gate. If review changes into repair, start or resume a clarification run before the first write.

## Headless and stale-state handling

A headless invocation returns `clarification_required` with the current summary, questions, and resume identity. It must not create or modify the target. An interactive mediator may relay real user turns into the same run; the caller cannot mark itself as the user or select an express/fast path.

Recheck relevant authority and target hashes on resume and immediately before writing. When a relevant hash changes, run `invalidate`, identify affected questions, then run `reopen` for those stable IDs. Unrelated working-tree changes are recorded but do not restart clarification.

## Write boundary

The compact compliance trace records `clarify_boundaries` once when the iterative loop is complete and `receive_clarification_exit` once after valid user exit. These events attest to the interaction unless trusted runtime traces prove user identity.

After exit, persist the disposition, then snapshot the VDD baseline and define the contract. A clarification exit authorizes writing only; normal VDD validators still control `plan-ready`, phase authorization, implementation acceptance, and release authority.

If a sensitive value is discovered after persistence, append-only retention no longer applies. Use `quarantine`; it records a hash-only custody manifest, disposes every run-local evidence copy, and permanently blocks resume and promotion for that run. Do not attempt ordinary repair or restart after quarantine.

## Promotion boundary

Clarification state is not a repository-authority writer. Before a promotion can be prepared, freeze the S0 owner closure with independent producer and verifier output, then create a baseline from that verifier output:

```text
py -3 scripts/clarification_closure.py --repository-root <root> --skill-root <skill-root> --registry scripts/vdd-clarification-requirements.v1.json --producer-out <run>/closure-producer.json --verifier-out <run>/closure-verifier.json
py -3 scripts/clarification_baseline.py --repository-root <root> --closure <run>/closure-verifier.json --out <run>/baseline-control-assets.json
```

Promotion preflight shares the repository-canonical clarification target lock with every checkpoint, invalidation, reopen, supersede, and restart operation. A trusted approval nonce is reserved under that lock; a retry with the same promotion and candidate is idempotent, while another promotion cannot reuse it.

For a multi-file candidate, stage only immutable generation files and publish a single hash-bound committed-generation pointer after the complete generation verifies. Authority consumers that need transactional visibility must resolve content through that pointer and reject an absent, malformed, or mismatched pointer. Direct file readers are not transaction-aware consumers and therefore block multi-file promotion until their owner is migrated or the approved write set is reduced to one atomically replaceable authority object. A promotion result authorizes only the approved clarification projection write and explicitly excludes plan readiness, phase authorization, implementation acceptance, and release.
