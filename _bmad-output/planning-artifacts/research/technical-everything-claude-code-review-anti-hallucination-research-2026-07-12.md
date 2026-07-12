---
stepsCompleted: [1, 2, 3, 4, 5]
inputDocuments: []
workflowType: 'research'
lastStep: 1
research_type: 'technical'
research_topic: 'Everything Claude Code reviewer anti-hallucination and false-positive control'
research_goals: 'Verify ECC reviewer fact gates and false-positive rules, compare them with this repository, and recommend an actionable low-noise review standard.'
user_name: 'Administrator'
date: '2026-07-12'
web_research_enabled: true
source_verification: true
---

# Research Report: Everything Claude Code Review Anti-Hallucination

**Date:** 2026-07-12
**Author:** Administrator
**Research Type:** technical

---

## Research Overview

[Research overview and methodology will be appended here]

---

<!-- Content will be appended sequentially through research workflow steps -->

## Technical Research Scope Confirmation

**Research Topic:** Everything Claude Code reviewer anti-hallucination and false-positive control
**Research Goals:** Verify ECC reviewer fact gates and false-positive rules, compare them with this repository, and recommend an actionable low-noise review standard.

**Technical Research Scope:**

- Architecture Analysis - reviewer prompt, fact gate and output contract
- Implementation Approaches - evidence requirements, severity downgrading and zero-finding behavior
- Technology Stack - ECC agents, commands, hooks and supporting rules
- Integration Patterns - adaptation to this repository's code/document review workflows
- Performance Considerations - review noise, repeated rounds and trust cost

**Research Methodology:**

- Current GitHub data with exact repository/commit verification
- Primary-source inspection before secondary-source comparison
- File/line citations for critical claims
- Explicit confidence and applicability limits

**Scope Confirmed:** 2026-07-12

## Technology Stack Analysis

### Repository Identity And Delivery Form

The current upstream repository is [`affaan-m/ECC`](https://github.com/affaan-m/ECC), formerly discoverable through the Everything Claude Code name. This research pins commit [`40927950c49f6e742d341e20ff7b9b7e1e7bfff5`](https://github.com/affaan-m/ECC/commit/40927950c49f6e742d341e20ff7b9b7e1e7bfff5) so line-level conclusions do not drift with `main`.

ECC is primarily a repository-distributed agent harness rather than a conventional application service. Reviewer behavior is encoded in Markdown agent prompts, command documents and rule files; deterministic orchestration and regression checks are implemented in JavaScript/Node.js.

### Reviewer Prompt Layer

The generic reviewer is a declarative Markdown agent with tool permissions for repository reading, grep, glob and shell inspection. Its review pipeline explicitly requires diff collection, scope understanding, surrounding-code inspection and confidence filtering before output.

The anti-noise controls are not merely guidance in a README. They are part of the installed reviewer prompt:

- `>80%` confidence threshold.
- Four-question pre-report fact gate.
- Mandatory proof for HIGH/CRITICAL.
- Zero findings explicitly accepted.
- Named common-false-positive suppression list.

_Source: [`agents/code-reviewer.md` lines 19-110](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/agents/code-reviewer.md#L19-L110)_

### Deterministic Regression Layer

ECC protects the reviewer prompt with a Node.js regression test. The test asserts that the confidence filter, four-question gate, proof rule, zero-finding rule, false-positive heading and representative suppression patterns remain present. This is a textual contract test: it prevents accidental deletion, although it does not prove the model obeys the prompt at runtime.

_Source: [`tests/ci/code-reviewer-false-positive-guard.test.js` lines 1-82](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/tests/ci/code-reviewer-false-positive-guard.test.js#L1-L82)_

### Structured Multi-Agent Review Layer

ECC's native review workflow is JavaScript using Claude Code Workflow primitives. It fans out quality, language-specific and conditional security reviewers; validates their output with JSON Schema; deduplicates findings by normalized evidence; then sends every unique HIGH/CRITICAL item to an independent adversarial verifier.

Important implementation properties:

- Reviewer output is schema-constrained.
- HIGH/CRITICAL requires a `proof` field at the tool/schema layer.
- Clean diffs may return zero findings and `APPROVE`.
- Duplicate findings collapse before verification.
- Only a confident refutation (`isReal=false`, confidence at least `0.8`) clears a blocker.
- Reviewer or verifier failure is fail-closed, not silently treated as approval.

_Source: [`workflows/orch-review.workflow.js` lines 1-143](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/workflows/orch-review.workflow.js#L1-L143), [`lines 190-296`](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/workflows/orch-review.workflow.js#L190-L296)_

### Storage, Infrastructure And Deployment Relevance

The reviewed mechanism does not depend on a database, cloud service or durable server. Its core artifacts are repository files plus runtime workflow results. For adoption in this repository, the closest equivalents are:

- Markdown reviewer contracts under agent/workflow documentation.
- Machine-readable finding output and stable evidence fields.
- Deterministic contract tests guarding required reviewer clauses.
- Optional independent verifier stage for blocking findings.

This means the useful ECC pattern can be adopted without importing its whole harness or changing the Phase runtime architecture.

### Technology Assessment

Confidence is high for the prompt and workflow behavior because the claims are directly supported by pinned source files. Runtime effectiveness against real review corpora is not established by these files alone: the repository contains contract tests for prompt presence, but this step found no benchmark proving a measured false-positive reduction percentage.

## Integration Patterns Analysis

### ECC Review Pipeline

ECC separates review generation from blocker verification:

```text
unified diff
  -> quality/language/security reviewers
  -> JSON-Schema-constrained findings
  -> evidence-based deduplication
  -> independent verification of unique HIGH/CRITICAL
  -> blocking/advisory split
  -> human Gate 2
```

This separation is important. The first reviewer is allowed to discover candidates, but it does not have the final word on blocking severity. An independent skeptic attempts to refute each unique blocker. Only a confident refutation clears it; uncertainty and verifier failure remain visible blockers.

_Source: [`workflows/orch-review.workflow.js` lines 190-296](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/workflows/orch-review.workflow.js#L190-L296)_

### Structured Finding Protocol

ECC reviewer output uses a small protocol:

- `title`
- `severity`
- `file`
- optional `line`
- exact `evidence`
- `proof` for HIGH/CRITICAL
- optional concrete `fix`

The workflow enforces `proof` for blocking findings using JSON Schema conditional requirements. This is stronger than merely asking the model to be careful because malformed blocker output is rejected at the tool boundary.

However, ECC's workflow schema does not mechanically require a non-null line number, nor does it split proof into explicit input/state/outcome fields. Those stronger requirements currently live in the reviewer prompt. A repository adopting the pattern can make them required machine fields.

_Source: [`workflows/orch-review.workflow.js` lines 61-105](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/workflows/orch-review.workflow.js#L61-L105)_

### Deduplication Protocol

Independent reviewers often report the same defect with different titles or drifting line numbers. ECC deduplicates primarily on normalized offending evidence plus file path, retains the reporting dimensions and keeps the strictest severity.

This directly controls review amplification: adding more reviewer dimensions does not automatically multiply the number of user-visible findings. ECC reports a local example where 11 raw findings collapsed to 4 unique findings, but this is an anecdotal workflow test observation rather than a published benchmark.

_Source: [`workflows/README.md` lines 14-20](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/workflows/README.md#L14-L20), [`orch-review.workflow.js` lines 217-238](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/workflows/orch-review.workflow.js#L217-L238)_

### Human And Failure Gates

ECC keeps the final commit approval in the main conversation. A failed reviewer dimension prevents clean approval. A verifier failure does not erase the finding; it is returned as “could not be verified”. This preserves uncertainty instead of converting missing evidence into either confirmed truth or silent success.

For this repository, that distinction should be represented as:

- `confirmed`: proof passed fact gate and independent verification.
- `advisory`: real but non-blocking.
- `refuted`: verifier showed a false positive.
- `unverified`: insufficient verification; requires human decision, not repeated automatic findings.
- `rejected`: failed the initial evidence gate and is never shown to the user.

### Current Repository Integration Gap

The current general adversarial-review skill contains two rules that structurally force noise:

- “Find at least ten issues”.
- “HALT if zero findings — this is suspicious”.

These rules make zero findings impossible and reward speculative expansion. They directly contradict ECC's “clean review is valid” rule. Even though the later quick-dev triage can reject noise, the system still spends model calls, review rounds and human attention producing and classifying findings that should never have crossed the output gate.

_Local evidence: [`bmad-review-adversarial-general/SKILL.md` lines 25-36](C:/jimuyun/.agents/skills/bmad-review-adversarial-general/SKILL.md#L25-L36)_

The local Edge Case Hunter is materially better aligned: it limits itself to reachable changed paths, requires a trigger and consequence, and explicitly allows an empty array. Its output contract is a good base for the failure-scenario portion of an ECC-style fact gate.

_Local evidence: [`bmad-review-edge-case-hunter/SKILL.md` lines 31-68](C:/jimuyun/.agents/skills/bmad-review-edge-case-hunter/SKILL.md#L31-L68)_

### Recommended Interoperability Boundary

Do not import ECC wholesale. Introduce one repository-native `ReviewFinding` contract consumed by code review, document review and quick-dev review:

```text
findingId, artifact, startLine, endLine, exactEvidence,
triggerInput, requiredState, badOutcome,
contextRead, existingGuardAnalysis,
severity, severityRationale, confidence,
reviewDimension, status
```

Candidate reviewers may emit zero records. A deterministic gate drops records missing location, trigger/state/outcome or surrounding-context evidence. HIGH/CRITICAL additionally require exact evidence, guard-bypass explanation and defensible severity. Only surviving blockers enter an independent verifier; dedup occurs before verification.

### Integration Limitations

ECC's `orch-review` is explicitly described as a pilot, and this research found no dedicated integration test suite for the workflow itself. The strongest tested guarantee is currently that the generic reviewer prompt retains its guardrail clauses. Therefore the architecture is valuable, but its workflow implementation should be treated as a reference design rather than copied as a proven production component.

_Source: [`workflows/README.md` lines 1-20](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/workflows/README.md#L1-L20)_

## Architectural Patterns And Design

### Recommended Three-Stage Review Architecture

```text
candidate reviewers
  -> deterministic evidence gate and dedup
  -> independent HIGH/CRITICAL verifier
  -> confirmed/advisory/refuted/unverified result
  -> human decision only where required
```

The candidate reviewer discovers possible defects but cannot create a blocker directly. The evidence gate removes unsupported claims before they consume verifier or human attention. The verifier receives only deduplicated blockers and is prohibited from finding new issues during verification.

This follows ECC's Review→Dedup→Verify barrier while strengthening its machine contract for this repository.

_Source: [ECC PR #1817](https://github.com/affaan-m/ECC/pull/1817), [`orch-review.workflow.js` lines 190-281](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/workflows/orch-review.workflow.js#L190-L281)_

### Stage 1: Candidate Reviewers

- Zero findings is valid.
- No minimum finding count.
- Scope is changed lines plus the minimum surrounding dependency/test context needed to establish a failure.
- Candidate output is machine-readable and contains no prose-only finding.
- Review dimensions may be parallel, but they do not independently control severity or repeat the same evidence to the user.

The current local general adversarial skill must not remain in the blocking path while it mandates ten findings and treats zero as suspicious.

### Stage 2: Deterministic Evidence Gate

Use one repository-native `ReviewFinding` contract:

```text
findingId, artifact, startLine, endLine, exactEvidence,
triggerInput, requiredState, badOutcome,
contextRead[], existingGuardAnalysis,
proposedSeverity, severityRationale, confidence,
dimension, evidenceFingerprint, status
```

Drop before output when any of these are absent:

- exact artifact and current line range;
- evidence matching the reviewed revision;
- concrete trigger/state/outcome;
- context-read declaration covering relevant caller/callee/test or document authority;
- a reason the finding is not already handled.

HIGH/CRITICAL additionally require a precise guard-bypass explanation. If the proof is incomplete, demote to MEDIUM only when a concrete non-blocking failure remains; otherwise drop.

### Stage 3: Independent Blocker Verification

- Verify only deduplicated HIGH/CRITICAL candidates.
- The verifier may confirm, confidently refute or mark unverified.
- It may not add new findings.
- A confident refutation requires direct evidence; uncertainty does not become confirmation.
- `unverified` is a bounded human decision state, not permission for another autonomous discovery round.

ECC keeps uncertainty blocking. For this repository, that posture should remain for security/data-loss findings, while non-security unverified findings should pause for human classification rather than generate an endless repair loop.

### Stable Deduplication And Review Memory

Calculate `evidenceFingerprint` from normalized artifact path, line-anchored evidence hash, failure tuple and authority revision. Merge duplicate dimensions before verifier execution.

Persist final disposition:

- `confirmed`
- `advisory`
- `refuted`
- `unverified`
- `rejected`

A `refuted` or `rejected` fingerprint cannot reappear unless the evidence hash, relevant surrounding context, test result or authority revision changes. This is the missing control that prevents successive reviewers from rediscovering the same false positive under a new title.

### Bounded Review Lifecycle

- One discovery pass and one blocker-verification pass by default.
- A repair may rerun only findings whose evidence or affected path changed.
- MEDIUM/LOW do not trigger automatic repair/review recursion.
- Zero confirmed blockers ends the review.
- A new finding after repair must cite changed evidence or newly available authoritative context.
- Repeated unverified findings escalate once to the human and then pause.

### Code And Document Adapters

Code review context must name callers, callees, types/validation and tests. Document review context must name the exact clause, its authority owner, downstream consumer/validator and the conflicting path, field, status or action. Both use the same failure tuple and severity rules.

For document findings, “wording is unclear”, “could be more complete” and theoretical future inconsistency are not findings unless a named consumer can take a wrong action from the current text.

### Security Boundary

Diffs, findings and retrieved documents remain untrusted content. Schema validation limits output shape but does not establish truth. Independent verifier prompts must treat the candidate finding and diff as data, matching ECC's prompt-injection boundary.

### ECC Limitations To Avoid

- Do not copy broad file/function length rules as automatic HIGH severity.
- Do not allow a free-text `proof` field to substitute for trigger/state/outcome and guard analysis.
- Do not leave MEDIUM/LOW outside dedup and suppression memory.
- Do not claim measured false-positive reduction without a labeled review corpus.
- Do not treat ECC's pilot workflow as production-validated merely because its prompt clauses have a regression test.

## Implementation Approaches and Technology Adoption

### Technology Adoption Strategies

Adopt the pattern incrementally rather than importing ECC's complete agent harness. The first and highest-value change is to remove the local incentives that force fabricated volume: the general adversarial reviewer must no longer require at least ten issues or treat zero findings as suspicious. Replace those clauses with an explicit zero-finding-valid rule, the four-question fact gate, the HIGH/CRITICAL proof triplet and a repository-specific false-positive suppression list.

The adoption boundary should be one shared repository-native finding contract used by code, document and plan reviews. Existing reviewers become candidate producers; deterministic validation, deduplication and blocker verification become shared downstream stages. This preserves current specialized reviewers while preventing any one prompt from directly declaring a blocker.

_Source: [ECC PR #1817](https://github.com/affaan-m/ECC/pull/1817), [`agents/code-reviewer.md` lines 39-111](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/agents/code-reviewer.md#L39-L111)_

### Development Workflows and Tooling

The implementation should touch these local workflow surfaces in priority order:

1. P0: `.agents/skills/bmad-review-adversarial-general/SKILL.md` — remove minimum finding count and zero-finding suspicion; add evidence-gated output and suppression rules.
2. P0: `.agents/skills/bmad-quick-dev/step-04-review.md` and `.agents/skills/gds-quick-dev/step-04-review.md` — change the pipeline from reviewer-to-triage into candidate-to-gate-to-dedup-to-verifier; stop when no confirmed blockers remain.
3. P0: `.agents/skills/bmad-code-review/**` and `.agents/skills/gds-code-review/**` — align review, triage and presentation steps with the shared finding statuses and prevent reviewer-proposed severity from becoming final severity without proof.
4. P1: add a durable standard such as `docs/standards/llm-review-findings.md`, machine schemas such as `schemas/review-finding.v1.schema.json` and `schemas/review-disposition.v1.schema.json`, plus a deterministic validator.
5. P1: add stable evidence fingerprints and disposition memory so rejected or refuted findings cannot reappear without changed evidence or authority.

The verifier must receive only deduplicated HIGH/CRITICAL candidates, must not discover new findings, and must produce `confirmed`, `refuted` or `unverified`. MEDIUM/LOW remain advisory and do not trigger an autonomous repair-review loop.

_Source: [`orch-review.workflow.js` lines 190-296](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/workflows/orch-review.workflow.js#L190-L296)_

### Testing and Quality Assurance

Prompt-clause tests are necessary but insufficient. Add deterministic regression tests for behavior at the finding boundary:

- an empty finding array produces a valid clean review;
- a finding without an exact artifact and line range is rejected;
- a finding without trigger, required state and bad outcome is rejected;
- HIGH/CRITICAL without exact evidence or guard-bypass analysis is demoted or dropped;
- findings with the same evidence fingerprint collapse across reviewer dimensions;
- a refuted fingerprint cannot reappear against unchanged evidence;
- unchanged review input cannot generate a new blocker without new authority or test evidence;
- advisory findings do not trigger a repair loop;
- reviewer and verifier failures have explicit non-approval states;
- a document finding without authority owner and downstream consumer is rejected.

Retain prompt-presence tests similar to ECC's guard test, but add fixture-based validator tests and a labeled sample corpus. ECC's existing test proves guardrail text remains installed; it does not measure model compliance or precision.

_Source: [`code-reviewer-false-positive-guard.test.js` lines 1-82](https://github.com/affaan-m/ECC/blob/40927950c49f6e742d341e20ff7b9b7e1e7bfff5/tests/ci/code-reviewer-false-positive-guard.test.js#L1-L82)_

### Deployment and Operations Practices

Roll out in bounded stages:

1. Remove forced-finding rules immediately.
2. Run the schema and deterministic evidence gate in shadow mode on document and execution-plan reviews.
3. Enable deduplication and fingerprint memory.
4. Add independent verification for proposed blockers.
5. Promote the contract to blocking code review only after the labeled sample shows acceptable blocker precision.

Each review run should preserve raw candidates, rejected reasons, deduplicated findings and final dispositions as evidence. A rollback may restore the prior orchestration path, but must never restore the “at least ten findings” requirement.

### Team Organization and Skills

The repository needs one owner for the shared finding contract and validator, while each review skill retains ownership of its domain-specific context collection. Review authors must know how to demonstrate a reachable failure, distinguish current authority from future plans and reason about existing guards. Maintainers should calibrate severity using concrete impact rather than generic code-smell taxonomies.

Human involvement is limited to genuinely `unverified` blockers, security/data-loss risk and changes to the shared severity policy. Refuted and rejected findings should be handled automatically by stable disposition memory.

### Cost Optimization and Resource Management

The dominant savings come from eliminating unsupported candidates before additional model calls. Deduplicate before independent verification; verify only proposed blockers; do not send advisory findings into repair loops; and cap the default lifecycle at one discovery pass plus one verification pass.

Track raw findings, evidence-gate survivors, deduplicated findings and verified blockers separately. This reveals whether cost is being spent on discovery noise, duplicate dimensions or verifier uncertainty.

### Risk Assessment and Mitigation

The repository-specific false-positive list should include ECC's established cases and local recurring patterns:

- generic missing error handling when a caller or framework already handles the failure;
- missing validation on an internal function whose callers validate input;
- obvious constants, fixtures, examples or non-secret test values reported as harmful hardcoding;
- exhaustive switches, generated code or fixed tables reported merely for length;
- null, batching or await claims that ignore existing narrowing, fixed bounds or intentional fire-and-forget behavior;
- language migration and security-theater suggestions unrelated to a reachable defect;
- file or class size reported as a bug without a concrete changed-path failure;
- automatic interface extraction for every class;
- automatic DRY findings without bounded-context or change-cadence evidence;
- feature-local literals reported as missing global constants;
- missing comments that would only restate what the code does;
- theoretical future race or attack paths with no current trigger;
- demands for implementation evidence in planned or paused documents;
- treating plan-readiness PASS as a claim that code is complete;
- schema-tightening suggestions without a constructible invalid input and consumer failure;
- duplicate findings already owned by an upstream execution plan or authority;
- Windows, Godot or C# framework claims made without reading the relevant runtime behavior, callers and tests.

The main risk is false confidence: schema-valid output can still be factually wrong. Mitigate this with source-matching evidence checks, an independent verifier for blockers and a labeled review corpus. A second risk is under-reporting after removing forced volume; monitor accepted blocker recall on seeded defects rather than reintroducing a minimum finding count.

## Technical Research Recommendations

### Implementation Roadmap

- P0: remove forced issue count and zero-finding prohibition; add the fact gate and blocker proof rule to every blocking reviewer path.
- P1: introduce the shared schema, deterministic validator, evidence fingerprint, disposition memory and regression corpus.
- P1: align code, document, plan and quick-dev review output with a single lifecycle and bounded rerun policy.
- P2: run a fixed-sample or two-week shadow evaluation before making verified findings an automated gate.

### Technology Stack Recommendations

Use repository-native Markdown skill contracts, JSON Schema for machine output, a deterministic Python validator consistent with existing repository tooling and current log/evidence conventions. Do not add a database or import ECC's workflow runtime solely for this feature.

### Skill Development Requirements

Review skills should teach evidence collection, failure-tuple construction, context inspection, guard analysis, severity calibration and document-authority tracing. Verifier skills should be narrower: test the candidate claim, never broaden the review scope and never invent replacement findings.

### Success Metrics and KPIs

Measure:

- unsupported-finding drop rate;
- duplicate-collapse rate;
- confirmed-blocker precision;
- refuted HIGH/CRITICAL rate;
- repeated false-positive rate;
- median user-visible findings per review;
- legitimate zero-finding review rate;
- review rounds per change;
- human override rate;
- review time and model-token cost.

Do not optimize for fewer findings in isolation. The target is higher confirmed-blocker precision, lower repeated/refuted noise and more reviews closing in one bounded cycle.
