---
name: vdd-execution-plan
description: Clarify requirements before creating, restructuring, or repairing execution-plan document directories under strict Verification-Driven Development (VDD). Use when the user asks to create a VDD implementation plan, verification-driven execution plan, plan directory, executable contract/validator/behavior-slice workflow, or when the prompt names an existing execution-plan directory that must be audited and repaired across all Markdown, schemas, fixtures, validators, tests, ledgers, and source-coverage artifacts.
---

# VDD Execution Plan

Build execution plans in which executable verification controls development. Do not treat a plan as VDD merely because it contains testing sections.

Before acting, read [references/strict-vdd-standard.md](references/strict-vdd-standard.md) and [references/clarification-gate.md](references/clarification-gate.md) completely. Apply repository instructions and more specific nested instructions first.

When maintaining or evaluating this Skill itself, also read [references/skill-compliance-protocol.md](references/skill-compliance-protocol.md) and use `scripts/validate_skill_contract.py`.

## Select the mode

Choose exactly one mode.

### Repair an existing directory

Use repair mode when the prompt names a directory and it exists.

- Treat the complete directory as the target. Do not sample files.
- Include any original monolith, source requirement, recovery index, schema, fixture, validator, test, ledger, and coverage file required to prove semantic preservation.
- Repair every affected artifact needed for a coherent VDD control chain. Do not limit the change to the document where the first defect appears.
- Preserve historical review output and generated evidence. Add new run-scoped sidecars instead of rewriting history.

### Create a directory

Use create mode when the user asks for a new plan or names a target that does not exist.

- Honor an explicit target path or directory name.
- Otherwise follow the repository naming convention, normally `execution-plans/YYYY-MM-DD-<slug>/`.
- Start the plan as `draft`. Promote it to `plan-ready` only after its composite validator and negative fixtures pass.

If the named target is ambiguous between a file and directory, inspect local context first. Ask only when choosing would materially alter authority or overwrite unrelated work.

## Complete the pre-writing clarification gate

For create and repair modes, complete the gate in [references/clarification-gate.md](references/clarification-gate.md) before writing or modifying the target plan, schemas, fixtures, validators, tests, or product code. Pure read-only review does not trigger this write gate.

1. Load authority and inspect the current state read-only. Find discoverable answers instead of asking the user.
2. Persist clarification state outside the target plan with `scripts/clarification_state.py` under the repository evidence root, normally `logs/vdd-clarifications/<target-slug>/<run-id>/`. Coordination uses one repository-canonical target registry and cross-process lock independent of the selected evidence root; multiple local Codex sessions must resume the same active target run.
3. Discuss unresolved boundaries in dependency order. Each question round normally contains at least five same-level questions, stable `CQ-NNN` identities, a recommendation per question, and a confidence assessment. Fewer questions require an explicit same-level exhaustion reason; never invent filler.
4. Continue until the user explicitly states both that no further clarification is needed and that writing may begin. Agreement, encouragement, urgency, a high confidence score, or an initial prompt that pre-authorizes writing is not an exit.
5. Fail closed in headless mode. A caller may relay questions and resume the same run, but it may not simulate user confirmation or select a fast/express path.
6. Recheck authority and target hashes before writing. Invalidate the exit and reopen affected questions when relevant inputs changed.

The LLM may suggest ending clarification only at confidence `>= 90`, with no open blockers and all required boundary dimensions grounded. The user remains the only exit authority. If the user explicitly exits with blockers still open, writing may begin only in `draft`; clarification exit never proves `plan-ready`.

## Establish authority before writing

After the clarification gate exits, bind the confirmed boundary snapshot to the plan authority:

1. Re-read the repository routing instructions, current-state sources, standards indexes, architecture/ADR indexes, and relevant recovery files needed by the confirmed scope.
2. Inspect the target or neighboring execution plans without blind-scanning unrelated documentation.
3. Identify the approved intent source, current-state authority, durable standards, protected paths, downstream consumers, and non-goals. If BMad artifacts exist, inherit `SPEC.md`/companions/`.memlog.md`, stable `CAP-N`, `ARCHITECTURE-SPINE.md` `AD-n`, FR/NFR/UX-DR coverage, stories, and baseline commits without duplicating their authority.
4. Check Git status. Preserve unrelated user changes and never rewrite generated history.
5. For Phase service work, obey protected-path approval, compatibility, evidence, and UTF-8 rules from `AGENTS.md`.

Do not let plan prose become a second authority for an existing contract. Reference the durable owner and bind it by stable ID/hash where required.

## Build the VDD control chain

Implement this lifecycle:

```text
intent and invariants
  -> explicit spec delta plus executable contracts and acceptance identities
  -> validator plus positive/negative/mutation fixtures
  -> observed validator RED for the missing behavior
  -> smallest behavior slice
  -> implementation work
  -> fresh hash-bound validation evidence
       -> pass: authorize the next transition
       -> fail: structured diagnosis -> repair -> new hash-bound validation run
```

Route failures to the earliest invalid layer:

- wrong intent -> intent/authority;
- wrong contract -> executable contract;
- false or incomplete oracle -> validator/fixture;
- wrong decomposition -> behavior slice;
- behavior defect -> implementation;
- stale or conflicting evidence -> recovery/re-entry gate.

Never force every failure back only to the validator. Never weaken a validator to match an implementation without a contract change and a regression counterexample.

## Required plan artifacts

Adapt names to repository convention, but preserve these ownership roles:

```text
00-index.md
01-intent-authority-and-non-goals.md
02-executable-contracts-and-invariants.md
03-validators-fixtures-and-control-gates.md
04-behavior-slices-and-implementation-order.md
05-diagnostics-repair-and-reentry.md
06-testing-observability-and-evidence.md
07-implementation-phases.md
08-risks-dod-and-glossary.md
96-global-review-and-validation.md
97-requirements-ledger.md
98-source-to-split-audit.md
99-source-coverage.md
schemas/
fixtures/
tools/validate_all.py
tools/tests/
```

Existing plans may use a different split. Repair ownership and links rather than renaming files mechanically.

At minimum, machine artifacts must represent:

- stable requirement IDs, owner, first phase, acceptance ID, status, and source refs;
- `ADDED`, `MODIFIED`, `REMOVED`, or `RENAMED` deltas against the prior source/spec revision and hash;
- plan status and phase-transition predicates;
- executable contract schemas and allowed vocabularies;
- positive, negative, boundary, stale-evidence, and mutation fixtures;
- a repair baseline manifest with target/source/validator hashes and preserved baseline failures;
- a requirement-quality checklist separate from implementation tests;
- diagnostic records with failed rule, candidate hash, failure family, repair owner, rerun command, and next allowed state;
- phase-exit evidence and cross-run predecessor/supersession lineage;
- explicit distinction between plan readiness, phase authorization, implementation acceptance, and release authority.

## Put verification in the control position

Create one version-controlled composite entry such as `tools/validate_all.py`. It must:

- run structural, semantic, schema, link, source-coverage, fixture, unit, and mutation checks;
- return nonzero unless the requested readiness predicate passes;
- emit machine-readable rule IDs and bounded diagnostics;
- reject stale inputs, missing context classes, open blockers, orphan requirements, duplicate owners, uncovered acceptance IDs, and invalid phase transitions;
- distinguish a successful command invocation from a passed plan/phase status;
- never live only under `logs/`;
- never claim implementation completion from plan consistency.

Its authorizing output must use a versioned result envelope with run/predicate/status, candidate/current/source hashes, validator version, rule-level checks, diagnostics, `authorizes`, and `does_not_authorize`. A `pass` with mismatched hashes, skipped required checks, an unregistered predicate, or authority sets that differ from the predicate's exact machine contract is invalid.

Do not build a keyword-count validator. Parse the actual contracts and prove both valid and invalid fixtures. Test the validator by mutating required books, owners, phases, schemas, evidence, state transitions, hashes, and failure classifications.

Before implementation authorization, run at least one invalid or mutation fixture and observe the expected stable failure ID. A test merely written or a validator source marker does not prove RED.

If a protected or independent verifier is required, separate it from the repository-local plan validator. Freeze its rule/version identity before it authorizes downstream work.

## Control LLM-assisted review

When the plan uses LLM reviewers:

- reviewers produce candidates only;
- zero candidates are valid; never require a minimum finding count;
- a deterministic gateway validates exact evidence, current hashes, failure tuple, context closure, guard analysis, authority, consumer, validator, severity, and scope;
- dedup identity includes evidence root, failure tuple, finding family, route/version, and authority revision so distinct failures on the same lines are not collapsed;
- P0/P1 require an independent verifier; P2 remains advisory unless policy explicitly says otherwise;
- required context classes map to concrete manifest artifacts rather than self-reported labels;
- execution model, reasoning, tool probe, process/session identity, and reviewer/verifier separation are attested when they affect authority;
- complete-read is described as an attestation unless tool traces independently prove it.

## Repair workflow

1. Inventory every target artifact and its inbound/outbound authority links.
2. Write a baseline manifest with relative paths, hashes, source/validator versions, and current state; then run existing validators/tests read-only and preserve baseline failures.
3. Declare explicit requirement/spec deltas and build a gap matrix against every section of the strict VDD standard.
4. Repair intent, contracts, validators, fixtures, slices, diagnostics, ledgers, source coverage, and status claims in dependency order against a new candidate.
5. Keep generated views derived from machine owners; regenerate them only through their owner tool.
6. Run the composite validator, targeted tests, and all declared mutation cases against current hashes.
7. Confirm deliberate counterexamples fail with expected IDs and the repaired candidate produces a fresh valid result envelope.
8. If target or authority hashes changed after baseline capture, mark old evidence stale and start a new run/baseline.
9. Recheck Git status and report unrelated dirty files separately.

Do not close a gap with prose if its consumer is executable. Do not mark a finding closed without a stable fix reference, validation method, current evidence, and source authority.

## Creation workflow

1. Write intent, authority, non-goals, current-state boundary, and irreversible decisions.
2. Create the requirement registry and source coverage map before expanding detailed books.
3. Define spec deltas where prior behavior exists, executable contracts, state machines, acceptance IDs, requirement-quality checks, and failure families.
4. Implement the plan-local composite validator and positive/negative fixtures; observe the expected RED before authorizing product implementation.
5. Split work into thin vertical behavior slices, each naming consumed contracts, tests, evidence, rollback, and predecessor gate.
6. Define diagnostics, repair, re-entry, idempotency, evidence freshness, and cross-run lineage.
7. Add implementation phases, risks, stop conditions, DoD, global review, source audit, and coverage closure.
8. Run validation and retain `draft` if any required check is missing, skipped without authority, or open.

## Completion contract

Do not claim success until:

- every required artifact exists and has one clear owner;
- every active requirement maps exactly once to source, owner, phase, executable acceptance, and evidence intent;
- the composite validator and its tests pass;
- declared invalid/mutation cases fail with the expected stable rule IDs;
- the full proof command was freshly run against current candidate/source/validator hashes and its result envelope was parsed;
- no open blocker is hidden by a clean process exit;
- no validator, runtime config, or gate executable exists only in ignored runtime evidence;
- no future capability is documented as current;
- plan-ready, phase-authorized, code-complete, and release-ready remain distinct states;
- the final report states commands run, evidence written, residual gaps, and files changed.

If a production-grade schema validator, independent verifier, required context, or protected-path approval is unavailable, fail closed or leave the plan in `draft` with an explicit recheck condition.

## Maintain and evaluate this Skill

Use [references/skill-compliance-protocol.md](references/skill-compliance-protocol.md) for no-guidance, supportive, neutral, and competing scenarios. The shipped deterministic fixtures prove package contracts and action ordering; they do not prove fresh-context or cross-model behavior.

Run:

```text
py -3 scripts/validate_skill_contract.py --skill-root <skill-root>
py -3 -m unittest discover -s scripts/tests -p "test_*.py" -v
```

Keep zero findings valid, preserve stable failure IDs, and add a regression fixture whenever a real shortcut or rationalization is discovered. Report package validation, deterministic fixture validation, fresh-context observation, and cross-model stability as separate evidence levels.
