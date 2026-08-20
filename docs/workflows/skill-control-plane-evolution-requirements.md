# Skill Control-Plane Evolution Requirements

Status: `requirements-input`
Owner: repository maintainer
Scope: repository-local non-BMAD Skill control plane

## Purpose

This document is the explicit input for two sequential VDD plan operations.
It is not itself an execution-plan directory and must not be implemented as a
single code change. The maintainer will ask `vdd-execution-plan` to consume
each work package below and create or repair one complete execution-plan
directory at a time.

The work packages are intentionally ordered. A later package must consume the
accepted authority and public contracts produced by every earlier package.

## Global Boundaries

In scope:

- Repository-local control-plane Skills under `.agents/skills/`.
- Skill package contracts, examples, routing diagrams, dependencies,
  validation scripts, tests, references, and safety gates.

Out of scope:

- All BMAD Skills and all GDS Skills.
- `workflow-chapter2-repository-bootstrap` through
  `workflow-chapter7-ui-wiring-closure`; these Skills are explicitly excluded.
- Phase browser/API behavior, live runtime, Caddy, live metadata, hosted
  workspaces, authentication, shared LLM entrypoint behavior, and generated
  historical evidence.
- Automatic commit, release, deployment, archive, or protected-path approval.

## VDD Consumption Contract

For each package A and B:

1. Read this document and the repository authority named in `AGENTS.md`.
2. Create or repair a complete VDD execution-plan directory only because the
   maintainer explicitly requested that operation.
3. Select the least sufficient VDD profile. These packages change Skills,
   validators, routing, or lifecycle control and therefore normally require
   `self-hosted`.
4. Freeze package-specific sources, dependencies, write sets, read sets, and
   acceptance commands before implementation.
5. Do not infer completion from this document, assistant text, or a child Skill
   summary. Use the plan-local predicates and terminal validation.
6. Preserve failed evidence as append-only sidecars. Do not rewrite historical
   runs or evidence.

The order is strict:

```text
A Skill Authoring Standard
        |
        v
B Existing Skill Compliance Migration
        |
        v
Package A/B downstream implementation
```

If a package is blocked, stop the sequence. Do not start a dependent package
with an unaccepted or stale predecessor.

## Package A: Skill Authoring Standard

### Objective

Create an accepted repository-level standard and executable validator for
future and migrated Skills. The standard must be capability-aware so that
network, database, destructive, subprocess, and filesystem rules apply only
when the Skill declares the corresponding capability.

### Required outcomes

- A normative standard for Skill structure, scope, input/output contracts,
  examples, routing visualization, dependencies, references, scripts, tests,
  evidence, and security.
- A machine-readable `skill-contract.v1.json` shape or equivalent that every
  governed Skill can validate without adding unsupported frontmatter keys.
- A validator that checks, at minimum:
  - valid frontmatter and package name;
  - hard `SKILL.md` limit of 500 lines, with a recommended lower target;
  - one primary responsibility and explicit non-goals;
  - three ordered, materially different examples, each with Input and Output;
  - an ASCII decision tree or flowchart for routing/orchestration Skills;
  - declared dependencies, versions/authority, and missing-dependency output;
  - typed error outputs and fail-closed behavior;
  - script and test declarations for complex deterministic logic;
  - FAQ reachability, if a FAQ is present;
  - capability-conditioned secret, confirmation, database, prompt-injection,
    path, subprocess, network, HTTPS, and timeout controls.
- A test suite containing positive, boundary, and negative package fixtures.
- A migration policy explaining how existing Skills become compliant without
  changing their business or lifecycle authority.

### Non-goals

- Do not make every Skill contain business-specific examples.
- Do not require a FAQ when no reusable FAQ decision exists.
- Do not require Context7 or network access for a local-only Skill whose
  behavior does not depend on external versioned APIs.

### Acceptance gate

Package A is complete only when the standard is accepted, the validator and
fixtures pass, and the standard itself has a clean package validation result.
No later package may cite a draft standard as authority.

## Package B: Existing Skill Compliance Migration

### Objective

Migrate these five existing non-BMAD, non-Chapter-2-7 Skills to the accepted
standard from Package A while preserving their current authority boundaries:

- `.agents/skills/vdd-execution-plan/`
- `.agents/skills/quick-dev-tdd-adapter/`
- `.agents/skills/run-phase-bootstrap-review/`
- `.agents/skills/run-refactor-implementation-acceptance/`
- `.agents/skills/maintain-knowledge-base/`

### Required outcomes

- Add route-focused examples rather than business-domain examples:
  - VDD create, direct-implementation boundary, invalid input;
  - Quick Dev strict-plan handoff, upgrade classification, invalid contract;
  - Bootstrap clean path, later-round confirmation, failed access/preflight;
  - Acceptance deterministic path, repair route, manual pause or stale input;
  - Knowledge Base existing-only refresh, targeted provisional result,
    publication/authority failure.
- Add concise dependency tables and typed standard error outputs.
- Add ASCII diagrams only where the Skill has internal routing or orchestration.
- Keep each Skill's main file below 500 lines; move detailed operational text
  to directly linked first-level references.
- Make every public entry independently invocable with explicit preflight and
  typed missing-dependency behavior. Do not remove legitimate child Skill
  dependencies.
- Add or extend deterministic validators and focused tests. Preserve current
  lifecycle ownership, fail-closed behavior, evidence rules, and protected
  boundaries.

### Acceptance gate

Package B is complete only when all five Skill packages pass the Package A
validator, existing Skill-specific tests remain green, and a route review shows
no authority, lifecycle, security, or compatibility regression.

## Cross-Package Stop Conditions

Stop and create a new repair/successor path when any of the following drifts:

- accepted standard, ADR, schema, validator, command, or dependency hash;
- declared write set, execution read set, or target containment;
- lifecycle owner or `authorizes` boundary;
- security capability classification or confirmation requirement;
- current child Skill public entry or output contract.

Never solve such drift by editing historical evidence, weakening a validator,
or silently applying a newer Skill contract to an old frozen plan.

## Recommended Execution Order

| Step | Operation | Required result before continuing |
|---:|---|---|
| 1 | VDD create/repair Package A | Accepted standard and passing validator |
| 2 | VDD create/repair Package B | Five Skills migrated and individually validated |
