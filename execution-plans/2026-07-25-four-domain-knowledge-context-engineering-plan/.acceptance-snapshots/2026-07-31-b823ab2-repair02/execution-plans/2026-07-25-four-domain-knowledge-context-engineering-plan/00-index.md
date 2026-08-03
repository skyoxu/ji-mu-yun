# Four-Domain Knowledge Context Engineering Execution Plan

- Title: Four-Domain Knowledge Context Engineering
- Status: implementation-complete
- Profile: resumable
- Plan ID: `jimuyun-four-domain-knowledge-context.v1`
- Branch: `main`
- Git Head: `7584f295c1b4d4124a4eaccc5ac51f05731ba923`
- Goal: Create a plan-local, verification-driven E1/E2 knowledge and context control plane with standardized deterministic maintenance and consumption before any Phase production-code change.
- Scope: ADR-0044, deterministic schemas, fixtures, requirement coverage, Knowledge Locator and maintenance contracts, read-only caller inventory, composition validator, K0-K14 implementation slices, and Bootstrap entry conditions.
- Current step: Implementation is complete; acceptance remains a separate external lifecycle decision.
- Last completed step: Quick Dev adapter evidence for K0-K14, E2 readiness, maintenance Skill coverage, and the plan-local implementation-completion predicate passed.
- Stop-loss: K0-K10 cannot touch live metadata, live Hosted workspaces, runtime, or Phase production code. K11-K13 production integration waits for BH-HANDOFF or formal merge/supersede decision plus explicit user authorization.
- Next action: Preserve this implementation evidence and seek a separate acceptance decision when the required external acceptance scope is defined.
- Recovery command: `py -3 execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/validate_whole_directory.py`
- Open questions: Acceptance scope and any operational rollout decision remain separate from this completed implementation plan.
- Exit criteria: All plan-local artifacts parse and compose, Locator/maintenance fixtures return exact outcomes, inventory reproduces from the current source snapshot, every active requirement has a slice and acceptance reference, whole-directory validation passes, and the Quick Dev completion predicate observes current K0-K14 evidence; Bootstrap evidence stays supplemental and non-authorizing.
- Related ADRs: `docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md`, `docs/adr/ADR-0033-phase-metadata-sqlite-local-disk.md`, `docs/adr/ADR-0035-phase-controlled-runner-workspace-execution.md`, `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`, `docs/adr/ADR-0038-phase-evidence-sidecars-readback.md`, `docs/adr/ADR-0040-phase-c-hardening-before-scaleout.md`
- Related decision logs: n/a (decision is captured by ADR-0044)
- Related task id(s): n/a (user-authorized plan creation)
- Related run id: `logs/ci/2026-07-25/kc-plan-r1e` (finalized `blocked`; immutable historical evidence)
- Related latest.json: n/a (no hosted route run)
- Related pipeline artifacts: `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/`

## Authority and lifecycle

The original standalone Markdown remains the original-requirements input. This directory is the resumable VDD execution plan and becomes the plan-local authority after its validator publishes `plan-ready`. ADR-0044 is the new Accepted Phase decision. It extends ADR-0037, complements ADR-0038, and supersedes neither.

The lifecycle is `draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`. The composition validator may publish only `plan-ready`; the Quick Dev adapter's plan-local completion predicate may publish only `implementation-complete` after all current slice evidence is present. Neither mechanism authorizes acceptance, handoff, release, deployment, or archive.

## Directory map

| Artifact | Purpose |
| --- | --- |
| `01-scope-authority-and-non-goals.md` | Authority, scope, protection and explicit user constraints |
| `02-executable-contracts-and-invariants.md` | Observable contract and fail-closed invariants |
| `03-validators-fixtures-and-control-gates.md` | Schema, fixture and composition-validator contract |
| `04-behavior-slices-and-implementation-order.md` | K0-K14 slices with RED/GREEN and write boundaries |
| `05-testing-observability-and-evidence.md` | Test matrix and append-only evidence locations |
| `06-risks-dod-and-glossary.md` | Risks, definition of done and vocabulary |
| `07-implementation-phases.md` | Phase gates and resumable execution sequence |
| `08-bootstrap-review-entry.md` | Conditions for a later `bootstrap-upstream-plan` run |
| `09-plan-local-artifact-conventions.md` | Naming, hash and scope conventions |
| `implementation-contract.v1.json` | Machine-readable slices, dependencies and write policy |
| `schemas/` | Plan-local JSON Schemas, including Locator and maintenance request/result contracts |
| `fixtures/` | Positive and negative executable fixture inputs, including standardized knowledge interfaces |
| `requirements-ledger.v1.json` | Machine requirement ledger |
| `tools/build_hosted_inventory.py` | Read-only source inventory generator |
| `tools/validate_whole_directory.py` | Composition validator and plan-ready publisher |
| `95-implementation-evolution-and-completion-report.md` | Append-only resumable implementation report |

## Safety declaration

This plan repair writes only repository requirements/decision documentation and plan-local artifacts. It does not create the planned Skill or Locator implementation, start Phase A, access the live SQLite database, read or modify `logs/phase-a-innernet/workspaces/**`, create a canary in a real host root, call a provider, or run Bootstrap Review.
