---
document_type: vdd-source-brief
status: proposed
scope: repository-toolchain-control-plane-only
repository: skyoxu/ji-mu-yun
repository_ref_reviewed: fd5a8fdeaaadaf579c9e388b6233ec87d560fd83
created_date: 2026-08-03
---

# Toolchain Control Plane Core Skill Evolution — VDD Source Brief

## 1. Purpose

This document is a normative source brief for `vdd-execution-plan`.

It directs VDD to create and evolve **independent requirement directories** for the long-term improvement of the repository Toolchain Control Plane. It combines:

- unfinished matters exposed by `execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/`;
- the approved Toolchain Workflow Evidence Catalog architecture;
- the current project constraint that this is an AI-native, single-maintainer, single-repository system;
- the decision that core Toolchain Skills evolve through evidence, evaluation, versioned deltas, and maintainer governance rather than through an autonomous SkillOS or an assumed RL endpoint.

This brief is not an implementation plan and grants no lifecycle authority.

## 2. Hard scope boundary

### 2.1 In scope

Only the repository Toolchain Control Plane is in scope:

- `.agents/skills/vdd-execution-plan/**`;
- `.agents/skills/quick-dev-tdd-adapter/**`;
- `.agents/skills/run-phase-bootstrap-review/**`;
- `.agents/skills/run-refactor-implementation-acceptance/**`;
- repository-owned Toolchain routing, validation, evidence, replay, evaluation, and governance utilities under `scripts/sc/**` or another explicitly approved Toolchain root;
- Toolchain-owned execution-plan evidence under `execution-plans/**`;
- Toolchain-owned append-only derived evidence under a dedicated `logs/**` root that is not Phase hosted state.

### 2.2 Explicitly out of scope

The following are forbidden in every directory created from this brief unless a later, separately approved source brief changes the boundary:

- `PhaseA.Platform/**` and `PhaseA.Platform.Tests/**` product/service behavior;
- `runtime/phase-a/**`;
- `logs/phase-a-innernet/**`;
- Hosted project workspaces;
- browser/API user workflows;
- account-, project-, tenant-, credential-, billing-, or sandbox-owned evidence;
- front-end GDD or game-module creation;
- project-level or game-domain Skills;
- user conversation memory or user-project training data;
- automatic online self-modification;
- unrestricted Self-Questioning;
- percentage-based traffic canaries;
- an RL execution plan or an assumption that RL is the final state.

Any required change crossing these boundaries must stop the current VDD plan and request a separate source brief.

## 3. Operating model for the Toolchain Control Plane

### 3.1 Fixed core Skill set

The default core capability set is stable:

1. `vdd-execution-plan`;
2. `quick-dev-tdd-adapter`;
3. `run-phase-bootstrap-review`;
4. `run-refactor-implementation-acceptance`.

Normal evolution changes a version, contract, policy, CLI, evaluator, router, fixture, or deterministic guard of an existing core Skill. Normal evolution does **not** create a second permanent Skill for the same function.

The following operations are exceptional architecture changes and require their own VDD plan and ADR:

- create a new first-level core Skill;
- delete a core Skill;
- merge two core Skills;
- split one core Skill into multiple first-level Skills;
- transfer lifecycle or decision authority between core Skills.

A/B and shadow candidates may coexist temporarily, but only one stable production entry exists for one formal function.

### 3.2 Primary evolution loop

The Toolchain Control Plane SHALL evolve through the following loop:

```text
Producer-owned evidence
    -> cross-run problem observation
    -> core Skill delta
       + evaluation delta
    -> deterministic/surrogate validation
    -> historical replay
    -> bounded new-task shadow or eligibility cohort
    -> maintainer disposition
    -> versioned stable update or rollback
```

A Skill change without an evaluation change is incomplete unless the plan proves that existing evaluation already covers the changed behavior.

### 3.3 Adapted CoEvoSkills principle

For this repository, CoEvoSkills means **Skill implementation and Skill evaluation co-evolve**. It does not mean that the repository continuously creates, merges, or deletes Skills.

Every meaningful core Skill candidate SHOULD contain:

- the Skill/CLI/policy delta;
- applicability and non-applicability boundaries;
- positive fixtures;
- negative fixtures;
- at least one regression case when the change fixes a historical defect;
- evaluation commands;
- expected observable results;
- rollback target;
- source-evidence references.

### 3.4 Cross-run comparison, not generic business similarity

Historical value comes primarily from different requirements passing through the same core Skill or workflow stage. Analysis SHOULD group by:

- target Skill;
- workflow stage;
- route decision;
- failure family;
- reuse decision;
- evidence gap;
- recovery path;
- cost or convergence behavior.

It SHOULD NOT assume that two requirements are useful merely because their business semantics are similar.

### 3.5 Self-Questioning and RL

Core Skills MUST NOT autonomously generate questions, change their own rules, update their own evaluation baseline, and approve the result.

A bounded evaluator may propose a counterexample or missing test as a **non-authorizing evaluation-gap candidate**. A maintainer or a separate governed plan must approve its admission into an evaluation set.

RL is not a committed roadmap directory. If a stable narrow decision problem later exceeds deterministic, statistical, supervised, or learning-to-rank baselines, a new source brief may evaluate learned decision support. That future brief must not presume RL.

## 4. Current repository facts and unfinished matters

### 4.1 Existing Refactor Acceptance extension

`execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/` currently records:

- `state = implementation-complete`;
- no authority for `acceptance-passed`, `release`, or `archived`;
- one primary real consumer: `execution-plans/2026-08-01-workflow-model-routing-control-plane/`;
- three closed repair families:
  - `candidate-baseline-contamination`;
  - `self-hosted-knowledge-read-set-collision`;
  - `toolchain-policy-architecture-index-gap`.

These repair families are valuable evaluation seeds, but they are not yet proven universal cross-plan Skill Memory.

### 4.2 Replay portability gap

The historical terminal validator directly invokes a machine-specific absolute path:

```text
C:/Users/Administrator/.codex/skills/.system/skill-creator/scripts/quick_validate.py
```

This is acceptable as historical evidence of the original machine, but it is not a stable long-term replay contract. Historical evidence must not be rewritten. A new repository-owned replay/validation wrapper and compatibility receipt are required for future evaluation.

### 4.3 Evaluation gap

The completed plan proves implementation conformance and downstream consumer replay. It does not yet provide a longitudinal quality baseline for `run-refactor-implementation-acceptance` across independent plans and lineages.

The following remain absent:

- stable-versus-candidate Skill comparison;
- Anchor, Frontier, Challenge, and Holdout sets;
- explicit label provenance and missingness;
- hard-gate plus Pareto comparison rules;
- cross-plan quality and cost cohorts;
- a versioned Skill quality baseline distinct from Git candidate identity.

### 4.4 Existing Evidence Catalog directory

The repository already contains:

```text
execution-plans/2026-07-31-toolchain-workflow-evidence-catalog-v1/
```

It is `plan-ready` and already defines the pull-only catalog, producer registry, Entity/Artifact/Relation/Projection/Generation Envelope model, four adapters, bounded CLI, publication/LKG separation, and detached closure fixture.

VDD MUST NOT create a duplicate or replacement Evidence Catalog directory merely because this source brief is newer.

Before implementation, VDD must repair/revalidate that existing directory against current `main`, including Toolchain changes added after its original baseline. The existing profile-upgrade rule remains authoritative: upgrade from `resumable` to `self-hosted` only if implementation must modify an existing producer route, schema, lifecycle publisher, or controlling validator.

## 5. Normative first-class requirement-directory manifest

This section is a first-class architectural contract.

Each row is an **independent first-class requirement directory**. VDD MUST NOT merge rows into one monolithic directory, nest one row as an implementation slice of another row, or let one row publish another row's lifecycle state.

Every directory must have its own:

- frozen knowledge context;
- baseline and candidate identity;
- requirements and acceptance IDs;
- implementation contract and ordered slices;
- command registry;
- plan state and resume state;
- terminal validator;
- rollback or disable path;
- Refactor Acceptance target after implementation;
- append-only evolution/completion report.

| ID | Directory name | Status | Profile | Dependency | Creation rule |
| --- | --- | --- | --- | --- | --- |
| `TC-E0` | `2026-07-31-toolchain-workflow-evidence-catalog-v1` | Existing, `plan-ready` | `resumable`; conditional `self-hosted` upgrade | Current repository facts and repaired plan inputs | **Do not create. Repair/revalidate, implement, and accept the existing directory.** |
| `TC-D1` | `toolchain-core-skill-replay-portability-and-evaluation-seed` | New | `self-hosted` | Current Refactor Acceptance extension | **Create now. This is the only new directory authorized for the current VDD invocation.** |
| `TC-D2` | `toolchain-workflow-evaluation-and-observability-baseline` | Future first-class directory | `resumable`; `self-hosted` if controlling validators change | `TC-D1` and `TC-E0` acceptance-passed | Create only after dependencies pass and real Catalog outputs are frozen. |
| `TC-D3` | `ordinary-fast-ship-combined-review-shadow` | Future first-class directory | `self-hosted` | `TC-D2` baseline and label provenance | Create independently; never merge with context-loading work. |
| `TC-D4` | `toolchain-context-loading-measurement-and-progressive-experiment` | Future first-class directory | `self-hosted` | `TC-D2` context/cost metrics | Create independently; never merge with review-topology work. |
| `TC-D5` | `core-skill-observability-memory-and-miner-shadow` | Future first-class directory | `resumable` | `TC-E0`, `TC-D2`, and sufficient independent cohorts | Create only after sample-gate evidence exists. |
| `TC-D6` | `core-skill-version-governance-and-git-rollback` | Future first-class directory | `self-hosted` | `TC-D5` plus real Skill deltas and maintainer dispositions | Create only after governance inputs exist. |

There is no committed `TC-D7` for RL.

## 6. Dependency graph and creation order

The dependency graph is not a single narrative chain:

```text
TC-D1 -> repair/revalidate TC-E0 -> implement/accept TC-E0 -> TC-D2

TC-D2 -> TC-D3
TC-D2 -> TC-D4

TC-E0 + TC-D2 + independent-sample gate -> TC-D5
TC-D5 + real candidate/decision history -> TC-D6
```

VDD must create one directory at a time. Future directory names in this brief are first-class reservations, not permission to pre-create empty directories.

## 7. Current mandatory VDD output: TC-D1

### 7.1 Required directory

VDD SHALL create exactly one new requirement directory with a date-prefixed repository name equivalent to:

```text
execution-plans/<date>-toolchain-core-skill-replay-portability-and-evaluation-seed/
```

The plan ID should remain stable and date-independent:

```text
toolchain-core-skill-replay-portability-and-evaluation-seed
```

Profile: `self-hosted`.

### 7.2 TC-D1 outcome

TC-D1 must make future core Skill replay and evaluation portable without rewriting historical evidence, and must convert the useful findings from the 2026-08-01 Refactor Acceptance extension into explicitly non-authorizing evaluation-seed records.

### 7.3 TC-D1 requirements

VDD must define stable requirement and acceptance IDs covering at least the following:

1. Preserve every byte and lifecycle state in `2026-08-01-refactor-acceptance-toolchain-compact-vdd`; no retroactive rewrite or auto-migration.
2. Add a repository-owned Skill-package validation/replay entrypoint for future terminal validators.
3. The entrypoint must not depend on a hard-coded user profile or absolute Codex Skill path.
4. The entrypoint must resolve the actual validator through a bounded capability contract and record the resolved path, version, and content identity in a non-authorizing receipt.
5. Missing, substituted, drifted, or incompatible validator capability must fail closed.
6. Add a compatibility replay record for the historical machine-bound validation step without claiming that the old command was portable.
7. Create an append-only evaluation-seed manifest for the three historical repair families, with exact native evidence references and hashes.
8. Mark every seed as `anchor_candidate`, `challenge_candidate`, or another explicitly non-baseline candidate class. No seed may become an accepted quality baseline in TC-D1.
9. Define a stable-versus-candidate replay matrix for the affected Refactor Acceptance surfaces.
10. Re-run the downstream `workflow-model-routing-control-plane` terminal consumer as a higher-level replay, without treating one consumer as proof of universal quality.
11. Keep all outputs non-authorizing except the plan's own normal VDD/implementation/Acceptance lifecycle.
12. Provide a deterministic terminal validator and a disable/rollback path.
13. Avoid modifying Phase service, hosted runtime, browser/API, user projects, or sandbox behavior.
14. Avoid introducing Experience Memory, Miner, Curator, promotion, learned ranking, or RL.

### 7.4 TC-D1 evaluation seeds

The seed manifest must preserve exact source references and express cautious hypotheses:

| Failure family | Initial candidate role | Required caution |
| --- | --- | --- |
| `candidate-baseline-contamination` | Anchor candidate | Likely cross-plan, but must be replayed against independent dirty-baseline fixtures. |
| `self-hosted-knowledge-read-set-collision` | Challenge candidate | May be specific to self-hosted context construction; do not generalize to all VDD/Acceptance tasks. |
| `toolchain-policy-architecture-index-gap` | Challenge candidate | Represents closed-policy coverage risk; do not assume every new directory prefix belongs in the policy. |

### 7.5 TC-D1 authority boundary

TC-D1 must not retroactively publish `acceptance-passed` or `archived` for the 2026-08-01 historical plan by editing its state. Any new disposition must be a separately authorized append-only artifact whose authority is defined by the current repository lifecycle contracts.

Because TC-D1 may change a Toolchain validator or an Acceptance-adjacent contract, its plan must explicitly prevent self-approval. Bootstrap review, deterministic validation, and maintainer disposition must remain separate from the candidate implementation.

## 8. Existing TC-E0 repair/revalidation instructions

After TC-D1 reaches `acceptance-passed`, VDD must repair the existing Evidence Catalog directory rather than create a new one.

The repair must audit at least:

- current `main` drift from the original catalog baseline;
- the Toolchain review domain and compact-VDD prerequisite bundle;
- Acceptance route selection, Bootstrap launch, and import as distinct relations;
- focused repair verification evidence;
- manual-pause closure evidence where producer contracts expose it;
- nested `.acceptance-snapshots/**` and copied control-plane exclusions;
- adapter compatibility with current producer-native schemas;
- whether any required adapter support forces the plan profile to upgrade to `self-hosted`.

The repair must not broaden v1 into Phase hosted evidence, Experience Memory, Miner, or governance.

## 9. TC-D2 contract: Workflow Evaluation and Observability Baseline

TC-D2 is an independent first-class directory. It must distinguish:

```text
Candidate identity baseline
    Git/content identity of one implementation candidate

Skill quality evaluation baseline
    Versioned evidence used to compare stable and candidate Skill behavior
```

TC-D2 must implement:

### 9.1 Observable baseline

Initial metrics may include only directly observable facts, such as:

- token count;
- wall time;
- attempt count;
- semantic review round count;
- transport failure count;
- artifact count;
- context bytes;
- prompt bytes;
- reuse attempted/accepted/rejected and rejection reason;
- manual pause;
- maintainer disposition presence;
- missing evidence fields;
- mapping status.

Metrics such as false negative, false positive, later-discovery rate, missed P1, repair effectiveness, Skill Memory contribution, and counterfactual success require a separate label-provenance contract, observation window, and holdout.

### 9.2 Evaluation-set classes

TC-D2 must make the following first-class:

- **Anchor Set** — durable critical regressions and authority failures;
- **Frontier Set** — current representative best-known task shapes;
- **Challenge Set** — adversarial boundaries, missing inputs, stale evidence, and ambiguous cases;
- **Holdout Set** — excluded from candidate construction and used only for final comparison.

### 9.3 Comparison policy

Candidate evaluation must use:

```text
hard gates
    + Pareto comparison
    + maintainer disposition
```

Hard gates include no new P0/P1 miss, no lifecycle-authority regression, no evidence-traceability regression, no new unauthorized write, and no protected-boundary bypass.

Optimization metrics may include lower cost, lower time, smaller context, fewer invalid retries, lower maintainer intervention, and higher first-pass convergence. A weighted total score must not override hard gates.

## 10. TC-D3 contract: Ordinary Fast-Ship Combined Review Shadow

TC-D3 is a separate self-hosted experiment. It must not replace or weaken full Bootstrap Review.

It must define:

- a distinct `ordinary_fast_ship_combined` candidate mode;
- deterministic hard escalation to full Bootstrap for security, auth, authority, ADR, protected path, release, evidence-control-plane, and high-risk lifecycle changes;
- shadow-only operation before activation;
- fixed eligibility cohorts and explicit task counts rather than traffic percentages;
- comparison against the TC-D2 baseline;
- rollback to the existing review route;
- no review-input navigation projection unless separate evidence proves it necessary.

## 11. TC-D4 contract: Context-Loading Measurement and Progressive Experiment

TC-D4 is a separate self-hosted experiment. It must first measure:

- command identity;
- requested and loaded context classes;
- source count;
- context bytes;
- prompt bytes;
- excluded context classes;
- context manifest hash;
- cost and elapsed time.

The first progressive-loading candidates should be read-only or thin orchestration commands. Semantic reviewer, verifier, gate, and finalization inputs must not be reduced until an independently accepted experiment proves semantic equivalence and fail-closed behavior.

## 12. TC-D5 contract: Core Skill Observability Memory and Miner Shadow

TC-D5 is not a production Skill-adoption system. Its first release is read-only and maintainer-facing.

It should answer questions such as:

- where each core Skill repeatedly blocks;
- which route/reuse decisions recur;
- which evidence gaps are discovered late;
- which recovery paths consume unusual cost;
- which deterministic checks may be moved earlier;
- which maintainer overrides recur.

Pilot order is mandatory:

1. Exact Reuse rejection reasons;
2. cost and missingness;
3. repair patterns only after multiple independent plans and lineages, time separation, and at least one counterexample.

The Miner may use deterministic classification plus non-authorizing LLM explanation. It must not freely infer causal relations from raw logs, modify a Skill, update an evaluation baseline, or inject advice into a production core Skill.

## 13. TC-D6 contract: Core Skill Version Governance and Git Rollback

TC-D6 replaces the idea of a general autonomous Curator platform with narrow single-maintainer governance.

It must support:

- register one explicit delta to an existing core Skill;
- bind the Skill delta and Evaluation delta;
- run TC-D2 evaluation and bounded shadow/replay;
- record maintainer disposition append-only;
- publish one stable version through an explicit command;
- retain the previous stable version as a Git-backed rollback target;
- rollback without deleting failed candidate history.

It must not automatically:

- create, delete, merge, or split first-level core Skills;
- promote a candidate;
- rewrite historical evidence;
- replace the maintainer decision;
- convert Catalog projections into governance authority.

The Evidence Catalog may index governance evidence on a later rebuild, but governance owns its own append-only native decision store.

## 14. Cross-directory acceptance rules

For every directory in the manifest:

1. Completion is local to that directory.
2. A terminal validator cannot publish another directory's state.
3. Producer-native evidence remains owned by the producer.
4. Derived outputs use `authorizes: []` unless a current lifecycle contract explicitly states otherwise.
5. Historical evidence is append-only and is never rewritten to make replay easier.
6. New fixtures must identify whether they are Anchor, Frontier, Challenge, Holdout, or non-baseline exploratory candidates.
7. Every fixed historical defect must add or bind a regression evaluation unless the plan records why existing coverage is sufficient.
8. Every candidate has an explicit rollback or disable path.
9. Unknown or missing data remains unknown/missing; it is not coerced into failure or success.
10. A directory must stop if implementation requires Phase service, hosted workspace, account, browser/API, or user-sandbox changes.

## 15. Required VDD behavior when consuming this brief

For the current invocation, VDD must:

1. create only `TC-D1`;
2. use `self-hosted` profile;
3. bind current `main`, this source brief, the 2026-08-01 Refactor Acceptance plan, relevant Accepted ADRs, and current Skill contracts;
4. generate stable requirement, acceptance, slice, command, lifecycle, resume, knowledge-context, and terminal-validation artifacts;
5. include a first-class section named **First-Class Directory Boundary** stating that TC-D1 cannot absorb TC-E0 or TC-D2–TC-D6;
6. include a first-class section named **Historical Evidence Preservation**;
7. include a first-class section named **Skill Delta Plus Evaluation Delta**;
8. include a first-class section named **No Autonomous SkillOS Or RL**;
9. stop before implementation authorization;
10. report any conflict between current repository authority and this brief instead of silently normalizing it.

VDD must not pre-create TC-D2–TC-D6, must not create a duplicate TC-E0 directory, and must not place future directory contracts inside TC-D1 implementation slices.

## 16. Source references for VDD

VDD should inspect at least:

- `AGENTS.md`;
- `README.md`;
- `.agents/skills/vdd-execution-plan/SKILL.md`;
- `.agents/skills/quick-dev-tdd-adapter/SKILL.md`;
- `.agents/skills/run-phase-bootstrap-review/SKILL.md`;
- `.agents/skills/run-refactor-implementation-acceptance/SKILL.md`;
- `execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/00-index.md`;
- `execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/requirements.v1.json`;
- `execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/plan-state.v1.json`;
- `execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/95-implementation-evolution-and-completion-report.md`;
- `execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/tools/validate_implementation.py`;
- `docs/adr/ADR-0053-refactor-acceptance-toolchain-compact-vdd.md`;
- `execution-plans/2026-07-31-toolchain-workflow-evidence-catalog-v1/00-index.md`;
- `execution-plans/2026-07-31-toolchain-workflow-evidence-catalog-v1/01-requirements-and-acceptance.md`;
- the uploaded architecture revision that defines the pull-only Evidence Catalog and first-class directory split.

## 17. Final directive

The repository is not building a general Skill marketplace or autonomous SkillOS.

The target is a fixed set of core Toolchain Skills that improve transparently through:

```text
observability
-> cross-run problem evidence
-> Skill delta + Evaluation delta
-> replay and bounded shadow
-> maintainer disposition
-> versioned update or Git-backed rollback
```

VDD must preserve that target in every directory created from this brief.
