# Package B canonical requirements (fresh rebuild)

## FR-1 Applicable common constraints


In scope:

- Repository-local control-plane Skills under the .agents/skills directory.
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


## FR-2 Six original migration requests

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

## FR-3 Current authority and difference migration


- `docs/standards/skill-authoring-standard.md` and Accepted ADR-0062 own the
  quality standard. `scripts/sc/validate_skill_quality.py` is the existing
  strict/inventory public validator, with its existing policy and schemas.
  Package B must not implement a second validator or edit Package A's oracle.
- Use the existing `skill-quality.v1.json` sidecar shape. Keep only name and
  description in frontmatter. Reuse existing operational references and
  substantive declarations; add a separate guide only when details need to
  leave the main file. Do not create five parallel documentation frameworks.
- The five public workflows, their Q1/Q7/Q8/Acceptance/publisher gates, typed
  errors, caller-session transport and content-bound execution reuse already
  exist. Add quality declarations and focused migration checks, not replacement
  runtimes. A historical pass is not current verification.
- BMAD wrappers, official native installation, administrator read-only consumer
  registration and per-run local configuration forwarding are separate already
  committed work. They are background only, excluded from Package B writes.
  Device configuration and local paths remain ignored.

### Five-package difference map

| Package | Existing capability to reuse | Remaining migration work and observable checks |
| --- | --- | --- |
| VDD | `scripts/vdd/compile_plan.py`; planning, clarification, governance-mode, lifecycle, resume and native semantic validation | Add a valid quality sidecar, dependencies and create/direct-input/invalid-input primary examples. Keep plan-ready distinct from implementation and Acceptance; retain atomic source/contract coverage and native repair. |
| Quick Dev TDD | `scripts/quick_dev/run.py`; observed behavior routing, first-use JSON/Python/TOML, bounded authoring, RED/GREEN/REFACTOR, Q6, Q7/Q8 and execution reuse | Add quality metadata and strict-plan/upgrade-boundary/invalid-contract examples. An upgrade is a typed route to the owning VDD boundary, not automatic approval or BMAD fallback. Keep exact cases, failure IDs, write scopes, and per-unit budgets. |
| Bootstrap Review | `.agents/skills/run-phase-bootstrap-review/scripts/bootstrap_review.py`; explicit existing profile/preflight/round and model-route controls | Add quality declarations and clean/later-round/access-failure examples without a new review framework. Replace machine-specific validation commands with actual repository-owned checks. Keep later-round and consumer authority intact; no automatic extra reviewer in this migration. |
| Refactor Acceptance | `.agents/skills/run-refactor-implementation-acceptance/scripts/run_acceptance.py`; existing prepare/coordinator/action and finalization owners | Add quality declarations and deterministic/repair/manual-or-stale examples. Preserve action registry, authority, current proof and finalization requirements; Q8 alone is not acceptance-passed. |
| Knowledge maintenance | `.agents/skills/maintain-knowledge-base/scripts/maintain_knowledge.py`, the request helper and native publisher | Add quality declarations and existing-only/targeted-provisional/publication-failure examples. Preserve main-bound source ownership, failed sidecars, LKG and explicit publication. Do not hard-code an obsolete suite count. Operator-requested needs a real target/main and maintainer confirmation, but no stale-route artifact; catalog-stale-maintenance retains its verified Acceptance route. |

Dependency declarations must identify real prerequisites, authority/version and
missing/mismatch outcomes. The adopted schema resolves package-local JSON
id/version records; a minimal non-authorizing declaration record may be needed.
Such a record documents an adopted contract version, not proof that Python,
Codex, a model, an external dependency or publication was installed or approved.
The native entry still checks actual runtime prerequisites. Preserve legitimate
child dependencies rather than claiming standalone means dependency-free.


## FR-4 Execution and evidence boundary


1. Inspect the five current packages, callers and focused tests; distinguish
   present behavior from missing quality metadata and stale prose.
2. Prepare a Package-B-only canonical requirements input with stable FR anchors
   and source-role/hash mapping. Include applicable global/consumption/drift
   constraints; exclude Package A implementation and unrelated BMAD artifacts.
   Cite existing files as file paths, function names as separate text, and
   directories as explanatory directories rather than malformed file inputs.
3. Use the public VDD compiler with the self-hosted plan-shape profile, because
   these are control-plane packages. Native workers and gates own plan-ready.
   VDD does not execute RED or emit future execution proof.
4. Quick Dev performs controlled probes. Present behavior gets current
   regression/terminal; missing behavior needs a real bound RED before Q4 and
   GREEN/REFACTOR. Absent imports, files or test runtimes are not behavioral RED.
   A genuine host admission defect is repaired narrowly with positive/negative
   tests before final input freezing, never by weakening the failure oracle.
5. Freeze common inputs before final proof. Reuse matching content/coverage/
   environment-bound native originals, not summaries or Git SHA alone. Keep
   failed evidence. Each independent unit retains 1800 seconds total and 600
   seconds without genuine progress; retries share bounded cumulative cost.
6. Run each of the five strict Package A public checks, relevant owning-package
   regressions and a route-boundary check. Preserve under-500-line main files,
   typed dependency failures and capability-aware security controls. Use actual
   supported local test dependencies; do not relabel Linux as Windows.
7. Formal inputs, implementation, plans and native evidence stay in the original
   repository. Save content-hashed stage snapshots and verify restoration;
   preserve an authorized durable copy outside the ephemeral environment.
   A missing old candidate cannot be reconstructed by copying success states.


## FR-5 Completion and non-goals


The migrated five packages must pass the existing strict validator; directly
affected existing tests remain green and route checks show no authority,
lifecycle, security or compatibility regression. The complete plan must retain
all six requests and explicit test/case coverage. Native implementation-complete
is only Quick Dev completion. The requested independent A/B review and any
necessary repair come before the separately owned final Acceptance workflow.
Neither a sidecar nor a passing validator grants workflow or publication power.

Do not add a global runtime enforcement platform, daemon, database, MCP service,
new model-selection policy, blanket external-version gate or new approval system.
Do not change Phase services, BMAD/GDS, Chapter 2-7, accepted Package A authority,
private device configuration, existing budgets/security permissions or historical
receipts to make this migration pass. GitHub publication/merge and unrelated
Windows full workflows are not automatic parts of this cloud implementation.


## FR-6 Source drift and repair


Stop and create a new repair/successor path when any of the following drifts:

- accepted standard, ADR, schema, validator, command, or dependency hash;
- declared write set, execution read set, or target containment;
- lifecycle owner or `authorizes` boundary;
- security capability classification or confirmation requirement;
- current child Skill public entry or output contract.

Never solve such drift by editing historical evidence, weakening a validator,
or silently applying a newer Skill contract to an old frozen plan.


Source provenance: `docs/workflows/skill-control-plane-evolution-requirements.md`, Package B plus applicable shared sections only. Package A implementation text is an accepted prerequisite, not an additional scope.
