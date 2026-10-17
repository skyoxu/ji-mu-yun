---
id: SPEC-tc-d1-trustworthy-skill-replay-and-evaluation-repair
package_schema: canonical-spec-package.v1
companions:
  - path: _bmad-output/specs/spec-tc-d1-trustworthy-skill-replay-and-evaluation-repair/requirements-and-acceptance.md
    role: normative_companion
  - path: _bmad-output/specs/spec-tc-d1-trustworthy-skill-replay-and-evaluation-repair/domain-contract.md
    role: normative_companion
  - path: _bmad-output/specs/spec-tc-d1-trustworthy-skill-replay-and-evaluation-repair/authority-and-open-questions.md
    role: normative_companion
  - path: _bmad-output/specs/spec-tc-d1-trustworthy-skill-replay-and-evaluation-repair/atomic-obligations.md
    role: normative_companion
  - path: _bmad-output/planning-artifacts/architecture/architecture-tc-d1-trustworthy-skill-replay-and-evaluation-repair-2026-09-12/ARCHITECTURE-SPINE.md
    role: adopted_companion
  - path: _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-09-11/addendum.md
    role: adopted_companion
sources:
  - path: _bmad-output/planning-artifacts/prds/prd-jimuyun-2026-09-11/prd.md
    role: provenance
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are retained for traceability only.

# TC-D1 Trustworthy Skill Replay and Evaluation Repair

## Why

The repository must prove that it validated the requested Skill package with the intended trusted validator, executed meaningful stable and candidate scenarios through real processes, exercised every current Consumer and rollback route, and produced evidence another operator can reconstruct. The current 08-05 implementation can create false confidence from wrong targets, weak validator identity, labeled but unexecuted matrices, partial Consumer coverage, or historical results; TC-D1 repairs that existing capability without taking authority from independent review or Acceptance.

## Capabilities

- **CAP-1**
  - **intent:** A maintainer can validate a repository-contained supported Skill package and a reviewer can prove which package was actually inspected.
  - **success:** Missing, non-directory, escaping, unsupported, substituted, or merely recorded targets fail; current VDD and Acceptance routes remain supported and successful evidence binds effective inspected content.
- **CAP-2**
  - **intent:** The system can rely on a bounded Validator Capability only after independently establishing its content, dependencies, compatibility, and discrimination behavior.
  - **success:** Missing, escaping, substituted, drifted, incompatible, self-selected, or always-success validators fail; valid and invalid independent Probes execute with bound inputs and outputs; candidate-controlled or self-reported identity cannot establish trust.
- **CAP-3**
  - **intent:** A reviewer can observe historical compatibility and the three retained evaluation seeds without converting historical or exploratory evidence into current authority or a quality baseline.
  - **success:** Historical tracked bytes and native identities remain intact; a current equivalent replay states its limits; each named seed occurs exactly once with approved non-baseline classification, provenance, applicability, missing labels, and a counterexample or explicit absence.
- **CAP-4**
  - **intent:** A maintainer can compare immutable, independently identifiable Stable and Candidate Packages across six materially distinct cases using real two-sided execution.
  - **success:** Valid package, invalid package, historical compatibility, dirty baseline, knowledge read-set collision, and closed-policy architecture-index cases each execute both subjects with distinct state and evidence; skipped, duplicate, copied, mislabeled, wrong-target, infrastructure-failed, or expectation-forged cases make the aggregate unsuccessful.
- **CAP-5**
  - **intent:** A reviewer can verify every authoritative Consumer and a maintainer can demonstrate enable, disable, behavioral rollback, and re-enable through each applicable real call surface.
  - **success:** A non-empty manifest is complete against repository callers and includes VDD, Acceptance, and workflow-model-routing observations; every applicable transition executes, rollback restores the Prior Route identity and verdict/diagnostic baseline, and omission or configuration-only switching fails.
- **CAP-6**
  - **intent:** A reviewer can navigate bidirectionally between every Atomic Obligation and its assertions, selectors, commands, witnesses, and runtime evidence.
  - **success:** All FR consequences, NFRs, guardrails, and retained historical sub-duties have sound-and-complete Exact Cover; behavioral duties have independent fault witnesses, other duties have deterministic violation witnesses, and no requirement, assertion, command, or evidence item is orphaned.
- **CAP-7**
  - **intent:** An Acceptance operator can reconstruct the semantic result from a fresh checkout and invalidate it whenever a result-determining input changes.
  - **success:** The Current Snapshot binds the Git baseline, Skill-input v2, code, fixtures, contracts, Consumers, tests, targets, validators, dependencies, sources, evidence, and any versioned normalization policy; reconstruction yields Semantic Reproduction and unexplained bound-input drift fails closed.
- **CAP-8**
  - **intent:** The toolchain can hand current implementation and review evidence to the proper lifecycle owner without allowing replay artifacts or assistants to authorize completion.
  - **success:** Replay, seed, matrix, review, and Quick Dev artifacts carry machine-verifiable empty authorization; historical Q8 and Acceptance cannot satisfy a new decision; only the current Acceptance lifecycle owner can publish `acceptance-passed` after required independent review and scoped approval.

## Constraints

- The detailed obligations and success measures in [requirements-and-acceptance.md](requirements-and-acceptance.md) are normative.
- Validator, package, matrix, Consumer, rollback, snapshot, evidence, and terminal semantics follow [domain-contract.md](domain-contract.md); unknown, stale, ambiguous, missing, or unverifiable facts fail closed.
- Authority boundaries and confirmation deadlines follow [authority-and-open-questions.md](authority-and-open-questions.md); this package grants no product-scope, Trust Approval, Consumer-exception, Acceptance, release, or archive authority.
- Historical `TC-D1-003` remains retained. Its `A05` source-root duty is narrowed only under the conditions in the authority companion; bounded, non-escaping, non-self-substitutable validator selection remains mandatory.
- Installed `_bmad/**`, `.agents/skills/bmad-*/**`, and `.agents/skills/gds-*/**` files are forbidden changes; permission to repair replay or Consumer code does not authorize writes there.
- Preserve tracked 08-01 and pre-repair 08-05 files byte-for-byte; add repair rounds and evidence append-only.
- Establish defect-revealing tests before production behavior changes. Existing passing brownfield behavior requires truthful characterization plus a distinct fault witness; fabricated RED or post-hoc failure evidence is invalid.
- Supported execution includes Windows, repository-relative identities, bounded subprocesses, bounded output, and deterministic terminal states; user-profile paths cannot establish current capability authority.

## Non-goals

- Creating another TC-D1 requirement tree, rewriting historical plans or evidence, or redesigning Skill-input v1/current-pointer semantics.
- Implementing TC-E0 or TC-D2 through TC-D6, creating quality baselines, admitting evaluation-set members, or promoting seeds, packages, or Skill versions.
- Changing Phase service, runtime, browser/API, accounts, Hosted workspaces, user sandboxes, installed BMAD/GDS Skills, or public product behavior.
- Adding Miner, Memory, Curator, autonomous Skill modification, SkillOS, learned ranking, percentage canaries, reinforcement learning, generalized governance, review-topology experiments, or cross-plan observability beyond TC-D1 evidence.

## Success signal

From a fresh checkout, an independent operator can select the bound current inputs, run every Probe, both subjects of all six Matrix Cases, every Consumer transition, and Exact Cover verification, then reproduce the semantic verdict from attributable real-process evidence. Wrong targets, invalid or drifted dependencies, always-success validators, illegal packages, zero-execution matrices, skipped Consumers, configuration-only rollback, stale snapshots, copied outcomes, and foreign authorization all prevent success.

## Assumptions

- Downstream Toolchain Consumers are direct internal users of this capability.
- Every external process and aggregate run will have an explicit timeout, bounded output capture, and deterministic terminal state; exact budgets depend on current baseline measurement.

## Open Questions

See [authority-and-open-questions.md](authority-and-open-questions.md). No unresolved authority may be assumed by Spec or Architecture.
