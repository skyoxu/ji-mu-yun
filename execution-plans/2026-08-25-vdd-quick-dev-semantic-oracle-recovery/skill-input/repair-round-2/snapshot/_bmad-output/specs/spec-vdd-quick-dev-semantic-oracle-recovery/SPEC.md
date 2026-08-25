---
id: SPEC-vdd-quick-dev-semantic-oracle-recovery
package_schema: canonical-spec-package.v1
companions:
  - path: _bmad-output/specs/spec-vdd-quick-dev-semantic-oracle-recovery/requirements.md
    role: normative_companion
  - path: _bmad-output/specs/spec-vdd-quick-dev-semantic-oracle-recovery/requirements-and-acceptance.md
    role: normative_companion
  - path: _bmad-output/specs/spec-vdd-quick-dev-semantic-oracle-recovery/open-questions.md
    role: normative_companion
  - path: _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-08-25/addendum.md
    role: adopted_companion
  - path: _bmad-output/planning-artifacts/architecture/architecture-vdd-quick-dev-semantic-oracle-recovery-2026-08-25/ARCHITECTURE-SPINE.md
    role: adopted_companion
sources:
  - path: _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-08-25/prd.md
    role: provenance
---

# VDD 与 Quick Dev 语义验证及独立裁判恢复

## Why

Ji Mu Yun 需要把 VDD 的验收意图转化为由真实进程产生、可审计且不可自证的验证结果。当前风险是候选 Quick Dev 复制预期结果、忽略 target、伪造矩阵通过或把 planned-only 报告误当完成。该 spec 建立从语义合同、冻结输入、独立裁判到 Acceptance ID 完成门禁的统一契约，同时保留旧计划只读兼容。

## Capabilities

- **CAP-1**
  - **intent:** VDD can define complete semantic verification intent for each active Acceptance ID, including oracle class, test selection, subject, case sources/producers, failure identity, expected observations, minimum execution and independent-judge requirement.
  - **success:** Semantic validation rejects missing fields, uncovered IDs, non-producer matrices, prose-only rollback, weak behavior RED and self-judging definitions; accepted coverage is sound-and-complete many-to-many, not an exclusive partition.
- **CAP-2**
  - **intent:** Quick Dev can preflight complexity and select a sufficient verification lane before execution.
  - **success:** The system records complexity class, lane, context lookup, minimum RED scope and upgrade conditions; semantic gaps route to VDD repair and unexpected green is handled as regression or proven existing behavior.
- **CAP-3**
  - **intent:** Quick Dev can freeze and execute a target through an independent oracle without trusting SUT-reported status.
  - **success:** Real process receipts and observations contain execution identity, hashes, counts, failure layers and actual matrix results; zero execution, drift, invalid identity or copied expected values cannot pass.
- **CAP-4**
  - **intent:** The toolchain can determine completion from exact Acceptance ID coverage and preserve evidence across valid runs.
  - **success:** `implementation-complete` requires current observations, receipts, non-zero execution, unchanged bindings and self-hosted independence; semantic observation and coverage artifacts provide traceability.
- **CAP-5**
  - **intent:** Self-hosted changes can be verified by a frozen predecessor or external judge while the candidate remains only the SUT.
  - **success:** Required false-green regressions are blocked, corrected fixtures pass, and the candidate is eligible as the next executor only after independent N→N+1 validation.
- **CAP-6**
  - **intent:** Quick Dev can publish machine-readable evidence state, verification outcome, failure family, failure ID, recommendation, reuse and recovery artifacts for an external coordinator.
  - **success:** `evidence_state` distinguishes planned, observed, recovered and invalid evidence; `verification_outcome` records run disposition; `failure_family` groups causes and `failure_id` identifies a deterministic case; recommendation-only output identifies next/forbidden actions and invalidated evidence; FR-17 requires publication only, not implementation of the top-level coordinator.
- **CAP-7**
  - **intent:** Execution profiles and change-impact rules can control cost and selective replay without lowering authenticity.
  - **success:** fast-ship, standard and self-hosted profiles preserve real execution, exact cover, non-zero cases, target/fixture binding and independent judging; semantic changes invalidate or recompute coverage as required.

## Constraints

- All FR, NFR and SM obligations in `requirements.md` are normative and stable.
- VDD defines intent only; it must not generate commands, receipts or hashes.
- Exact cover is sound-and-complete many-to-many coverage; multiple oracles may cover one Acceptance ID and one oracle may cover many IDs; exclusive partition is not required.
- Evidence state, verification outcome, failure_family and failure_id are separate layers and must not be conflated.
- Quick Dev must use real process execution, target/fixture binding and an independent judge; SUT self-report is not evidence.
- Legacy plans remain read-only compatible; new self-hosted completion cannot use the legacy contract.
- Review, commit authority, business-repository rules and Chapter 5 batch processing remain outside Quick Dev.

## Non-goals

- Distributed scheduling, remote sandboxes, containers/microVMs, object storage or multi-region disaster recovery.
- Top-level coordinator implementation; this package requires only the externally consumable recovery artifact.
- Acceptance/LLM review orchestration, Needs Fix reviewer coordination, commit authority, Godot/GdUnit/taskmaster/overlay rules and batch jitter/shard/quarantine.
- Bulk migration of old plans or mutation of Acceptance Skill, 08-05 implementation, historical snapshots/logs, README or plan governance.

## Success signal

An independent execution can trace every active Acceptance ID through a sound-and-complete many-to-many coverage graph to a real process receipt and observation, while planned-only, invalid, copied, drifted, timed-out and self-judged runs cannot reach `implementation-complete`. A downstream coordinator can consume the published recovery artifact without relying on chat context.

## Assumptions

- The product is an internal, self-hosted, single-node-first toolchain.
- An external coordinator exists or will consume the recovery artifact, but its implementation is not part of this package.
- Versioned JSON evidence can coexist with historical evidence without rewriting it.

## Open Questions

See `open-questions.md`; adopted architecture decisions close artifact authority, evidence snapshots, byte-level failure-ID construction and promotion ownership, while comparator policy, output normalization, judge operations, rollback probe, unexpected-green proof, stop-loss threshold and detailed semantic-change reuse remain intentionally Deferred.
