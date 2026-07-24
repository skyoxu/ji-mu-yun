# VDD Solo-Maintainer Simplification Requirements

- Status: review-candidate
- Date: 2026-07-24
- Target: `.agents/skills/vdd-execution-plan/**`
- Primary evidence: `execution-plans/2026-07-15-repository-maintenance-tdd-adapter/95-implementation-evolution-and-completion-report.md`
- Authority: explicit maintainer direction on 2026-07-24
- Document role: requirements only; this file does not authorize implementation, acceptance, archive, or release

## 1. Problem Statement

The current VDD Skill applies controls designed for multi-writer, externally reviewed, and adversarial evidence environments to a repository maintained by one trusted person with an AI assistant. The 2026-07-15 implementation showed that this default creates more plan-control work than product work.

The observed failure pattern was cumulative:

1. Plan readiness was treated as proof of complete future replayability.
2. Validator and evidence schemas expanded during implementation.
3. Broad hashes invalidated unrelated completed slices.
4. Historical runs were asked to satisfy lifecycle fields that did not exist when they ran.
5. Review became a requirements-discovery and implementation gate instead of supplemental design evidence.
6. A per-slice effect-fold candidate model conflicted with the repository's actual Git commit history.
7. Late S6/S7 repairs repeatedly triggered full S0-S7 replay before the local failure was stable.
8. Self-hosted proof, external trust roots, independent verifier identity, and crash-safe publication multiplied the control surface.

The Skill must retain truthful verification while removing controls that do not address the operating risks of this repository.

## 2. Operating And Threat Model

### 2.1 Assumptions

- One trusted human maintainer owns requirements and final decisions.
- One AI assistant performs planning and implementation work on the maintainer's behalf.
- Work may span sessions, but concurrent independent writers are not a design target.
- Git is the primary source of code identity, baseline history, and candidate comparison.
- Requirements are not injected by untrusted external reviewers, automated publishers, or third-party plan writers.
- The relevant failure modes are misunderstanding, omission, stale context, unintended scope, invalid tests, process interruption, and false completion claims.

### 2.2 Explicit Exclusions

The default VDD workflow shall not defend its own plan evidence against:

- malicious repository collaborators;
- forged reviewer identities;
- distributed writer races;
- external signature or attestation compromise;
- hostile mutation of finalized evidence;
- third-party requirement injection.

Product-facing security requirements remain in force. This simplification does not weaken authentication, authorization, data protection, destructive-operation approval, or runtime security tests for the product itself.

## 3. Goals

- G-001: Make `standard` the fast default for ordinary repository changes.
- G-002: Keep verification tied to observable behavior and current test results.
- G-003: Preserve separate plan, implementation, acceptance, and archive states.
- G-004: Reuse Git and existing repository validators instead of generating duplicate proof systems.
- G-005: Invalidate and rerun only affected slices until one terminal full validation is justified.
- G-006: Preserve enough recovery state for cross-session work without requiring distributed coordination.
- G-007: Keep 7-15 history intact while preventing its exceptional control plane from becoming the default template.
- G-008: Make every optional machine artifact justify a real consumer and a changed decision.

## 4. Non-Goals

- NG-001: Changing the Bootstrap Review control-plane implementation or its internal evidence protocol.
- NG-002: Changing Quick Dev implementation behavior in the same change.
- NG-003: Changing the future implementation-acceptance or archive Skills.
- NG-004: Rewriting historical 7-15 logs or retroactively fabricating RED, attempt, or lineage evidence.
- NG-005: Making a VDD plan validator an implementation acceptance authority.
- NG-006: Replacing product-specific security and compatibility requirements with this trust model.

## 5. Required Workflow Profiles

### 5.1 `standard`

This is the default for ordinary feature work, fixes, documentation changes, and bounded refactors.

Required controls:

- intent, scope, non-goals, and relevant authority;
- Git baseline and current dirty-scope observation;
- implementation slices or a single bounded change;
- a RED or regression command and an acceptance command;
- targeted validation during implementation;
- one terminal full validation before `implementation-complete`;
- the common lifecycle state marker.

It shall not require a custom schema, custom validator, 95 report, Bootstrap Review, external trust root, attempt ledger, or cross-slice effect fold unless another requirement makes that artifact necessary.

### 5.2 `resumable`

Use when work spans sessions, has multiple dependent slices, or can leave partial state.

Add only:

- a compact resume state;
- dependency-scoped slice status and invalidation;
- baseline and candidate identity;
- a 95 evolution/completion report and its index entry;
- recovery instructions for interrupted writes.

It shall not imply independent reviewers, signatures, or adversarial evidence custody.

### 5.3 `self-hosted`

Use only when the change modifies VDD, Quick Dev, acceptance routing, review routing, or a validator that controls the same workflow.

Add only the protocol fixtures and migration checks needed by actual consumers. Targeted validation must stabilize a changed layer before one authoritative end-to-end replay. External trust roots, verifier separation, signatures, and crash-consistent publication are not default requirements and require a separate explicit decision.

## 6. Functional Requirements

### 6.1 Clarification

- VDD-SOLO-001: The Skill shall inspect repository authority and current state before asking questions.
- VDD-SOLO-002: The Skill shall ask only questions whose answers materially change scope, compatibility, destructive behavior, or acceptance.
- VDD-SOLO-003: Zero clarification questions is valid when the request and repository state resolve the applicable boundaries.
- VDD-SOLO-004: There shall be no minimum question count and no numeric confidence threshold that independently blocks writing.
- VDD-SOLO-005: Explicit write authorization in the user's initial request is valid when no material blocker is discovered.
- VDD-SOLO-006: Clarification state shall be persisted only when unresolved decisions must survive a session boundary.
- VDD-SOLO-007: The default shall not require a repository-wide active-run registry, cross-process target lock, or reviewer identity attestation.

### 6.2 Plan Shape

- VDD-SOLO-010: The Skill shall select plan structure by complexity instead of requiring the fixed `00-08` and `96-99` document set.
- VDD-SOLO-011: A standard plan may consist of one plan document and one lifecycle state file while referencing existing repository test commands.
- VDD-SOLO-012: A plan shall add a custom schema or validator only when an actual machine consumer cannot use an existing repository contract.
- VDD-SOLO-013: Requirement, source, acceptance, and coverage mappings may share one owner artifact; duplicate ledgers and projections are prohibited unless they serve distinct consumers.
- VDD-SOLO-014: A generated artifact that cannot change a validation or routing decision shall be removed or remain optional.

### 6.3 Lifecycle And Authorization

- VDD-SOLO-020: The canonical lifecycle is `draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`.
- VDD-SOLO-021: One Skill-owned static transition contract shall replace plan-local copies of the full permission lattice.
- VDD-SOLO-022: The maintainer may explicitly authorize `implementation-authorized` without Bootstrap Review.
- VDD-SOLO-023: Bootstrap Review, when requested, remains supplemental evidence and does not publish a lifecycle state.
- VDD-SOLO-024: Quick Dev may publish only `implementation-complete`; acceptance and archive remain separately owned.
- VDD-SOLO-025: Old state names may be accepted only through an explicit compatibility adapter and shall not be emitted by new plans.

### 6.4 Verification And Replay

- VDD-SOLO-030: `plan-ready` proves that the intended implementation commands and acceptance path are actionable; it does not prove implementation completion or complete future evidence migration.
- VDD-SOLO-031: New behavior shall have an observed RED or controlled negative case before its implementation slice is accepted.
- VDD-SOLO-032: Existing behavior discovered after implementation may use a declared legacy/regression path; the Skill shall not fabricate historical RED evidence.
- VDD-SOLO-033: A RED command shall not depend on writes from the same slice's GREEN step or a future slice.
- VDD-SOLO-034: During repair, the Skill shall run the smallest targeted checks that prove the affected layer.
- VDD-SOLO-035: Targeted validation has no completion authority.
- VDD-SOLO-036: After all affected slices are stable, the implementation workflow shall run one current full validation before publishing `implementation-complete`.
- VDD-SOLO-037: A full replay from the first slice is required only when a shared lifecycle contract, global validator semantic, baseline identity, or dependency used by every slice changes.
- VDD-SOLO-038: A slice-local command, fixture, or implementation change shall invalidate only that slice and its declared downstream dependents.

### 6.5 Candidate And Evidence Model

- VDD-SOLO-040: The default candidate identity shall be a declared Git baseline plus either a frozen commit range or a complete scoped worktree identity. `HEAD` alone is valid only when the scoped index, tracked worktree, and relevant untracked set are clean. A dirty candidate shall bind `HEAD`, the canonical scoped tracked/index diff hash, and a manifest containing the path and content hash of every relevant untracked file.
- VDD-SOLO-041: Per-slice effect folding is optional and shall be used only when a real recovery consumer requires it.
- VDD-SOLO-042: Current contract, implementation, and validator inputs shall be freshness-bound, but append-only logs and explanatory reports shall not be part of the normative candidate hash.
- VDD-SOLO-043: Evidence migration shall choose among exact revalidation, affected-slice replay, full replay, or historical-only retention without inventing missing events.
- VDD-SOLO-044: Existing successful evidence remains historical evidence after invalidation; it shall not be rewritten or silently reused as current authorization.
- VDD-SOLO-045: Generic VDD Skill validation shall not depend on mutable files inside one specific execution-plan directory.
- VDD-SOLO-046: Generic Skill tests shall validate the 95 index contract with detached package fixtures. A repository-level execution-plan index validator, not the generic Skill package test, shall own live index ordering, containment, target existence, and report existence checks.

### 6.6 Review Policy

- VDD-SOLO-050: Bootstrap Review shall be optional unless the maintainer explicitly requests it or a separate protected-path rule requires it.
- VDD-SOLO-051: VDD shall not require three Bootstrap rounds for implementation authorization.
- VDD-SOLO-052: When review is requested, all accepted findings shall be repaired as one batch and deterministic targeted checks shall run before any later full review.
- VDD-SOLO-053: Review shall validate the requirements or implementation presented to it; it shall not become an unbounded requirements-discovery loop.
- VDD-SOLO-054: P2-only findings shall not automatically trigger another complete semantic review.

### 6.7 Platform And Recovery Controls

- VDD-SOLO-060: Path containment and protected-path approval remain mandatory when paths are changed.
- VDD-SOLO-061: Junction, reparse-point, path-case, CRLF, binary, and inaccessible-directory fixtures are required only when the change exercises those semantics.
- VDD-SOLO-062: Capsule revisions, attempt chains, accepted prefixes, and partial-write ledgers are required only for resumable workflows that can leave ambiguous state.
- VDD-SOLO-063: Single-writer state updates may use ordinary atomic file replacement; distributed lease and signer protocols are out of scope.

### 6.8 Evolution Report

- VDD-SOLO-070: `resumable` and `self-hosted` plans shall create a `95-*.md` report before implementation and update `execution-plans/95-implementation-report-index.v1.json` in the same change.
- VDD-SOLO-071: The 95 report is append-only, non-authorizing, and excluded from normative plan/candidate hashes.
- VDD-SOLO-072: The report shall record pre-completion plan corrections and a final implementation report after `implementation-complete`.
- VDD-SOLO-073: Standard plans may omit the 95 report unless requested by the maintainer.

### 6.9 Correct-Course Conditions

- VDD-SOLO-080: Two consecutive repair cycles dominated by new plan-control fields without new observable behavior shall trigger a simplification review.
- VDD-SOLO-081: A requirement to reconstruct an event that did not historically occur shall stop migration and select revalidation, replay, or historical-only retention.
- VDD-SOLO-082: If plan maintenance dominates implementation, the Skill shall reduce or split control-plane scope instead of adding another proof layer.
- VDD-SOLO-083: A self-hosted change shall stabilize its protocol contract before the final authoritative replay, but intermediate repairs shall use targeted validation.

## 7. Compatibility And Migration

- Existing plans and evidence shall not be retroactively invalidated solely because the Skill adopts this contract.
- A plan entering repair shall adopt the new lifecycle vocabulary and choose the least complex applicable profile.
- The 7-15 directory remains a historical `self-hosted` case. Its evidence shall not be rewritten to look like a `standard` plan.
- Existing 7-15-specific trust-root compatibility shall move behind a plan-owned or Bootstrap-owned compatibility validator. The generic VDD package may retain a detached interface fixture, but it shall not enumerate the live plan ID, dated directory, schema path, RMAP command IDs, predecessor hash, or current artifact bytes.
- Any change to another Skill or to the Bootstrap Review standard requires a separate scoped change; it shall not be hidden inside this VDD simplification.

## 7.1 Hardcoding Policy

The generic VDD Skill, package validator, and package tests shall not contain concrete dated execution-plan slugs, plan-local schema paths, RMAP identifiers, plan-specific predecessor hashes, user-profile paths, machine-specific absolute paths, or hashes of mutable live-plan artifacts.

Stable protocol constants are allowed when they are owned by the generic Skill or repository contract. These include lifecycle state names, schema versions, stable rule IDs, profile names, and the repository-relative `execution-plans/95-implementation-report-index.v1.json` contract path. Historical requirements and evidence documents may cite 7-15 paths and identities as explanatory sources, but generic runtime or package validation shall not consume those citations as authority.

## 8. Acceptance Criteria

- AC-001: Given a clear standard change request with explicit write authorization, the Skill can create a plan without asking filler questions or requiring a second authorization turn.
- AC-002: Given a standard plan that uses existing repository tests, validation does not require custom schemas, mutation fixtures, or Bootstrap Review.
- AC-003: Given a slice-local repair, only that slice and declared dependents become stale.
- AC-004: Given a shared validator semantic change, the workflow requires one final full replay after targeted stabilization.
- AC-005: Given already implemented legacy behavior, the workflow records the missing historical RED and uses current regression evidence without fabricating events.
- AC-006: Given explicit maintainer confirmation, `implementation-authorized` can be published without Bootstrap evidence and cannot imply later states.
- AC-007: Given a requested Bootstrap Review, its result remains supplemental and all findings are handled in a batch.
- AC-008: Given an ordinary business plan, filesystem edge fixtures and recovery ledgers are absent unless their triggering semantics apply.
- AC-009: Given a resumable or self-hosted plan, the 95 report is indexed, append-only, non-authorizing, and excluded from normative hashes.
- AC-010: Given the updated Skill package, its deterministic validation and unit/mutation tests pass, including standard, resumable, self-hosted, stale-slice, and competing-pressure fixtures.
- AC-011: The existing 7-15 directory and historical review evidence remain byte-preserved except for separately authorized additive records.
- AC-012: No generic VDD Skill source or self-test reads a mutable live execution-plan directory or embeds a concrete plan ID, dated directory, plan-local schema path, RMAP command ID, plan-specific predecessor hash, user-profile path, or mutable live-plan hash. Detached fixtures and repository-level live-index validation pass independently.

## 9. Proposed Implementation Order

1. Align lifecycle vocabulary and replace plan-local permission lattices with one Skill-owned transition contract.
2. Simplify clarification authorization and remove question-count, confidence, multi-writer, and identity-attestation gates.
3. Make plan artifacts profile-driven and collapse duplicate ledgers.
4. Implement dependency-scoped freshness and targeted-then-terminal replay rules.
5. Add conditional 95 reporting and compatibility behavior.
6. Move live 95 index validation to a repository-level owner and replace the package test with detached fixtures.
7. Remove generic Skill dependency on the live 7-15 trust-root instance through a plan-owned or Bootstrap-owned compatibility transition.
8. Update deterministic fixtures, behavior scenarios, package validation, and Skill routing metadata.

## 10. Decision Summary

The desired VDD model is verification-driven but not proof-system-driven. It must make incorrect completion difficult while keeping ordinary plan creation and implementation materially cheaper than the work being planned.
