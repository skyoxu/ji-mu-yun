# Toolchain Workflow Evidence Catalog v1 Execution Plan

- Title: Toolchain Workflow Evidence Catalog v1
- Status: implementation-authorized
- Profile: resumable
- Profile reason: The work spans dependent slices and sessions, but it adds a pull-only catalog without modifying existing VDD, Quick Dev, Bootstrap Review, or Acceptance routing, schemas, or controlling validators.
- Profile upgrade trigger: Upgrade to `self-hosted` before implementation if any existing producer control-plane route, schema, lifecycle publisher, or controlling validator must change.
- Plan ID: `toolchain-workflow-evidence-catalog-v1`
- Git baseline: `dbe2a731c9465946d3dc21ac3888491e33340c28`
- Baseline tree: `bb20a0f9ad45eadae2eb955dff56e9072e7a13ae`
- User intent: `docs/know8.txt` at SHA-256 `b3371f2fa9224fa3ea177e3466897358e17d2fdd80c4ac40d99eb4d982616e13`
- Goal: Build a deterministic, pull-only, non-authorizing catalog of formal repository Toolchain workflow evidence owned by VDD, Quick Dev, Bootstrap Review, and Refactor Implementation Acceptance.
- Current step: Route the authorized `TEC-S0` slice through Quick Dev without starting later slices.
- Recovery command: `py -3 -B execution-plans/2026-07-31-toolchain-workflow-evidence-catalog-v1/tools/validate_plan.py`

## Outcome Boundary

The catalog reads producer-owned formal evidence through an explicit producer registry and explicit roots. It emits immutable derived generations, validates native source hashes, and advances Current/LKG only through explicit publication commands. It never writes producer evidence, normalizes native lifecycle state, infers relations from proximity, or authorizes any workflow transition.

The v1 product surface is one repository-local Skill, `maintain-toolchain-workflow-evidence-catalog`, with stable schemas, four adapters, a bounded CLI, detached fixtures, and append-only runtime evidence under `logs/toolchain-workflow-evidence-catalog/`.

## Authority And Lifecycle

Authority order is `AGENTS.md`, Accepted ADRs, the frozen knowledge context, `docs/know8.txt`, this directory's machine contracts, then explanatory prose. Repository source and producer-native artifacts retain their existing authority. Catalog records and generations have `authorizes: []`.

The lifecycle is `draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`. VDD owns only `draft` and `plan-ready`. The maintainer owns `implementation-authorized`; Quick Dev owns only `implementation-complete`; Refactor Implementation Acceptance owns `acceptance-passed`. Bootstrap Review is optional supplemental evidence and publishes no lifecycle state.

## Machine Owners

- Requirements and acceptance: `01-requirements-and-acceptance.md`
- Implementation slices and boundaries: `implementation-contract.v1.json`
- Structured commands: `command-registry.v1.json`
- Frozen source bindings and scoped baseline: `authority-manifest.v1.json`
- Lifecycle state: `plan-state.v1.json`
- Resume state: `resume-state.v1.json`
- Knowledge context: `knowledge-context.v1.json` and `knowledge-context.freeze.v1.json`
- Plan-ready predicate: `tools/validate_plan.py`
- Current candidate identity: `tools/validate_all.py`
- Append-only continuity report: `95-implementation-evolution-and-completion-report.md`

## Implementation Order

`TEC-S0 -> TEC-S1 -> TEC-S2 -> TEC-S3 -> TEC-S4 -> TEC-S5 -> TEC-S6`.

`TEC-S0` fixes the narrow authority decision. `TEC-S1` fixes schemas, identity, registry, and path boundaries. `TEC-S2` implements pull-only producer adapters. `TEC-S3` builds and queries immutable generations. `TEC-S4` owns explicit publication and LKG recovery. `TEC-S5` proves the detached end-to-end protocol and hostile path boundaries. `TEC-S6` runs the terminal full validator and is the only slice allowed to publish `implementation-complete`.

## Safety

- Forbidden throughout: `logs/phase-a-innernet/**`, Hosted project workspaces, Phase runtime state, browser/API activity, account evidence, auth/security behavior, and producer-owned source or evidence mutation.
- Existing VDD, Quick Dev, Bootstrap Review, Acceptance, and Knowledge Base files are read-only inputs. Any necessary modification to them stops implementation and routes to VDD repair plus profile upgrade.
- The catalog accepts only explicit roots. There is no `scan-repository`, `discover-all-runs`, `infer-relations`, or `normalize-status` command.
- Raw prompts, environment values, secrets, and stdout/stderr bodies are neither copied nor printed by default.
- Existing unrelated worktree changes are outside this plan's scoped identity and must not be reverted or absorbed.

## Deferred Roadmap

All later roadmap priorities are non-goals for this directory: P1 evaluation/observability, combined-review shadowing, and context-loading experiments; P2 Experience Memory and Miner pilots; P3 Skill Candidate/Curator, promotion, eligibility cohorts, and rollback execution; and conditional P4 offline RL/ranking. No later VDD directory is pre-created by this plan.
