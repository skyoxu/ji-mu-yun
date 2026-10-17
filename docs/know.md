---
document_type: roadmap-source-brief
status: proposed
scope: repository-toolchain-control-plane-only
roadmap_ids: [TC-E0, TC-D2, TC-D3, TC-D4, TC-D5, TC-D6]
repository_ref_reviewed: 0dce7806c93e5e0ca4ac4faed61baa13735c8983
updated_date: 2026-10-17
tc_d2_repository_ref_reviewed: 971e53ebce52eb54a9f78bcd5bf0faa68aec61f4
tc_d1_source: docs/know-tc-d1-rebuild.md
---

# Toolchain Control Plane Skill Evolution Roadmap Source Brief

## 1. Purpose

This is the long-term source brief for TC-E0 and TC-D2 through TC-D6. TC-D1
has moved to `docs/know-tc-d1-rebuild.md` because the existing 08-05 directory
needs focused repair before it can satisfy a roadmap dependency.

This brief reserves independent outcomes and dependency gates. It is not an
implementation plan, does not authorize directory creation, and publishes no
lifecycle state. A future directory requires explicit user intent after its
dependencies are proven by current evidence.

## 2. Scope Boundary

In scope is the repository Toolchain control plane: current planning, TDD
implementation, review, Acceptance, Knowledge/Skill-input, evidence catalog,
evaluation, observability, and governance contracts under approved roots.

Out of scope are Phase service and tests, runtime/Caddy, hosted workspaces,
browser/API, accounts, credentials, user-sandbox evidence, game-domain Skills,
user-project training data, automatic self-modification or self-approval,
unrestricted self-questioning, percentage traffic canaries, and an assumed RL
endpoint. Crossing this boundary requires a separate source brief.

## 3. Operating Principles

The repository separates planning, implementation, review, Acceptance,
Knowledge selection, and evidence catalog lifecycles. Skill names and protocols
may evolve; future plans bind current entries instead of copying historical
2026-08 names.

```text
producer-owned evidence
-> cross-run observation
-> Skill delta plus evaluation delta
-> deterministic validation and historical replay
-> bounded shadow or fixed eligibility cohort
-> maintainer disposition
-> explicit stable update or Git-backed rollback
```

A Skill candidate includes applicability boundaries, positive and negative
fixtures, historical regressions, real commands and observations, rollback
target, and source evidence. Evaluation cannot authorize its own admission,
promotion, release, or Acceptance. Cross-run grouping uses Skill, workflow
stage, route, failure family, evidence gap, recovery, and cost/convergence;
generic business similarity alone is not a valid grouping rule.

## 4. Current Repository State

| ID | Current state | Roadmap interpretation |
| --- | --- | --- |
| `TC-D1` | Existing 08-05 directory with ADR and substantial implementation; round-6 Q8 is non-authorizing and review still reports semantic gaps | Repair from the separate D1 brief; no duplicate directory or satisfied dependency before fresh Acceptance |
| `TC-E0` | Existing Evidence Catalog directory, currently `implementation-authorized` | Revalidate against current repository and preserve the directory |
| `TC-D2` | No first-class directory | Blocked on current TC-D1 and TC-E0 Acceptance plus frozen real catalog output |
| `TC-D3` | No first-class directory | Blocked on TC-D2 baseline and label provenance |
| `TC-D4` | No first-class directory | Blocked on TC-D2 context and cost measurements |
| `TC-D5` | No first-class directory | Blocked on TC-E0, TC-D2, and a sufficient independent sample gate |
| `TC-D6` | No first-class directory | Blocked on TC-D5 plus real candidate and maintainer decision history |

Skill-input v2 is the live typed-source, immutable-generation, current-pointer,
and retention contract under ADR-0060. Future work must consume it where the
relevant Skill adopts that gate and must not recreate v1 current-receipt logic.

## 5. Independent Capability Boundaries

Each item remains an independent first-class requirement directory. It cannot
absorb another item, publish another lifecycle, or treat a plan as implementation
proof. A created directory owns its current sources, requirements, acceptance,
architecture, implementation contract, commands, state, resume behavior,
terminal predicate, rollback, and append-only evidence.

```text
TC-D1 fresh Acceptance ----+
                           +-> TC-D2 -> TC-D3
TC-E0 current Acceptance --+        -> TC-D4

TC-E0 + TC-D2 + independent sample gate -> TC-D5
TC-D5 + real candidate decisions         -> TC-D6
```

TC-E0 can be revalidated after the D1 boundary is stable. TC-D2 cannot start
until both upstream results are current and accepted.

## 6. TC-E0: Workflow Evidence Catalog

Continue `2026-07-31-toolchain-workflow-evidence-catalog-v1`; do not create a
replacement. Before implementation, revalidate its baseline, current producer
schemas, Skill-input v2 boundaries, nested snapshot exclusions, and profile.
Upgrade profile only if producer routes, schemas, lifecycle publishers, or
controlling validators must change.

The outcome remains a pull-only, non-authorizing catalog with explicit roots,
producer-native adapters, immutable generations, explicit publication, and
separate Current/LKG. It cannot scan arbitrary repository state, rewrite
producer evidence, normalize native lifecycle, infer authority from proximity,
or include Phase hosted/user evidence.

Revalidation must remove older adapters or relations superseded by current
mechanisms instead of preserving them for document parity. Every retained
adapter needs a current producer fixture and failure evidence.

## 7. TC-D2: Evaluation And Observability Baseline

TC-D2 distinguishes candidate Git/content identity from a versioned Skill
quality baseline. It consumes real TC-E0 output and accepted TC-D1 semantics.
The outcome is a repository evaluation and observation entry that carries a
routine evaluation from case selection to an evidence-backed comparison without
requiring the maintainer to switch Skills at every step.

This design borrows from the four modes, case format, evidence-based grading,
and repeated-run reporting in
[bmad-eval at cfba3ff5](https://github.com/bmad-code-org/BMAD-METHOD/blob/cfba3ff5f982c1809e060606e399f55ebd7bce5e/skills/bmad-eval/SKILL.md).
That snapshot is design input; integration binds the BMAD version actually
installed. This refinement does not revalidate the roadmap status rows above
or satisfy the TC-D1/TC-E0 dependency gates.

### 7.1 Ownership And A Continuous Evaluation Flow

TC-D2 complements bmad-eval; it does not replace it. TC-D2 owns versioned
evaluation sets, comparable observations, and consolidated reports. Reuse accepted TC-D1 replay for contract and validator behavior, and
TC-E0 references for producer evidence. Replay success does not prove agent
output quality. For agent evaluations, reuse compatible installed bmad-eval
runners and grading facilities rather than building a second harness or
copying its optimization loops.

Within an authorized evaluation, the TC-D2 entry selects the relevant cases and
mode, reuses a compatible recorded backend configuration, runs or imports the
evaluation, grades the evidence, and returns the comparison in the same flow.
Ask only for unresolved choices that affect the run. Ordinary observation and
accepted repository replay do not require a BMAD upgrade; capabilities whose
backend is absent or incompatible remain explicitly unavailable.

Standalone Skill benchmarking, first-time BMAD harness setup, description
optimization, and explicitly requested Skill-improvement sessions remain native
bmad-eval use cases. When a handoff is needed, carry the Skill identity, case and
rubric versions, comparison target, budget, and artifact references; import the
result into the same evaluation context without manual re-entry or an automatic
duplicate run. Keep producer-native artifacts intact and add only derived
bindings and observations. Do not reuse a result after its execution or grading
bindings change.

TC-D2 does not author or modify Skills, operate an improvement loop, or publish
a stable version. Improvement findings can inform maintainer work and later
TC-D5/TC-D6 inputs; native BMAD results grant no repository lifecycle authority.

### 7.2 Evaluation Questions And Discriminating Cases

Select the mode needed to answer the question; do not run all four modes for
every task or add a new gate to every delivery stage.

| Borrowed mode | TC-D2 question and intended use |
| --- | --- |
| Quality | Does this output satisfy the named assertions? Use for focused checks and regressions. |
| Variant | Does a candidate improve on the prior stable or stripped version on the same cases? Use for a concrete Skill delta or suspected unnecessary instructions. |
| Baseline | What does the Skill add over the bare model? Use when its added value is in question, not as a mandatory comparison for every run. |
| Trigger | Does the Skill load for intended requests and stay quiet for near misses? Use when applicability or routing changes; activation is separate from task success. |

Cases bind stable IDs, source provenance, realistic input, fixture identity,
and independently checkable assertions. Optional workflow-state prefixes may
reach a particular turn, but cannot prove real multi-turn recovery, state
transitions, or repository gates. Those claims need actual execution evidence.
Trigger cases include both should-trigger and near-miss should-not-trigger
labels and the recorded activation-detection method.

Pair artifact existence with substantive content checks. Include negative
assertions and observable process requirements where relevant: no unauthorized
writes, correct call ordering, and fidelity between source decisions and
outputs. Flag weak assertions that a wrong output can pass, and uncovered
outcomes. Preserve native BMAD cases where usable; keep repository provenance
and authority bindings alongside them rather than forking its case protocol.

### 7.3 Comparable Execution And Evidence-Based Grading

Bind each comparison to exact Skill, fixture, rubric, model, harness, and
relevant configuration identities. Use the same cases and declared conditions
on both sides. Isolate execution and stage required dependencies explicitly so
ambient project instructions or previous runs do not contaminate results.
A clean working directory is not a security sandbox: execution still obeys
repository-approved write and tool boundaries.

Prefer deterministic checks for facts observable in artifacts or transcripts.
Use a read-only semantic grader only where judgment is needed, with its rubric
and judge identity recorded and evidence cited per assertion. Grading must not
repair outputs, loosen assertions, or rerun a case until it passes. A runner's
successful exit means execution completed, not that its rubric or repository
gates passed.

Keep native verdicts and evidence unchanged. Separately distinguish assertion
failures, execution/time-out errors, grading errors, and unobservable results;
missing evidence cannot pass or be silently counted as a measured Skill defect.
An aggregate reports its denominator, missing cases, and failed attempts.

For stochastic agent evaluations, fewer than three repetitions per case and
configuration are a quick look, not a settled comparison. Three repetitions
alone do not establish statistical significance. Record the repetition and
retry budget before execution, retain all attempts, and report variation and
per-case regressions alongside aggregate differences. Do not impose repeated
agent runs on deterministic replay or passive observation.

### 7.4 Observations, Evaluation Sets, And Disposition

Initially collect only reproducible observations: command and implementation
identity, wall time, attempts, review rounds, transport failures, artifact and
context sizes, reuse decisions, manual pauses, maintainer decisions, missingness,
and mapping status. Token usage and monetary cost are optional measured fields
with provenance; unsupported usage remains unknown rather than estimated from
elapsed time. False-positive/negative, missed severity, later discovery,
repair effectiveness, causal contribution, and counterfactual success require
label provenance, observation windows, and holdout rules. Unknown stays unknown.

Evaluation sets are immutable per version:

- Anchor: accepted critical regressions and authority failures;
- Frontier: current representative task shapes;
- Challenge: adversarial and ambiguous boundaries;
- Holdout: excluded from candidate construction and opened for final comparison.

Freeze assertions and comparison conditions before candidate evaluation.
Changing them creates a new evaluation version, not a rewritten passing result.
A BMAD optimization test split is not automatically the TC-D2 Holdout: any case
or score used during construction or intermediate candidate selection cannot
serve as its untouched final holdout. Retain exposure history and report the limit of an imported comparison.

Disposition uses hard gates, Pareto comparison, and explicit maintainer judgment.
No weighted score overrides authority, security, traceability, protected-path,
nor unauthorized-write failures. Reports expose the concrete regressions,
uncertainty, weak assertions, and missing evidence behind an apparent gain;
they do not automatically approve, retire, or promote a Skill.

### 7.5 Minimum Evidence For The Future TC-D2 Implementation

Demonstrate a routine evaluation through one entry and a native bmad-eval
handoff/import without duplicate execution or loss of identity and evidence.
Show a deliberately wrong output failing a substantive assertion, and preserve
a native grading failure or missing observation without turning it into success.
Reject stale or incompatible imported bindings, preserve case-level regressions
when aggregate cost improves, and prove that a passing external benchmark
cannot publish Acceptance or a stable Skill version.

## 8. TC-D3: Ordinary Fast-Ship Review Shadow

TC-D3 evaluates a bounded combined-review candidate for eligible ordinary
fast-ship work without weakening the formal review route. It defines semantic
eligibility and hard escalation for security, auth, authority, ADR, protected
paths, release, evidence control, and high-risk lifecycle work.

Before activation it runs in shadow mode over fixed named cohorts and task
counts, compares against TC-D2, records disagreement and missed severity, and
restores the existing route on rollback. The old fixed mode name is discarded;
architecture should choose a current identifier. Review-input navigation is
excluded unless measurements prove it necessary.

## 9. TC-D4: Context Loading Experiment

TC-D4 first measures command identity, requested and loaded typed roles, source
count, bytes, transport coverage, exclusions, manifest identity, cost, and time
using Skill-input v2 concepts.

Progressive loading begins with read-only or thin orchestration. Reviewer,
verifier, gate, and finalization inputs may shrink only after independent
Acceptance proves semantic equivalence, complete coverage, stale-input rejection,
and fail-closed behavior. Typed roles and operation-required mappings supersede
the old generic “context classes” wording.

## 10. TC-D5: Observability Memory And Miner Shadow

TC-D5 is read-only and maintainer-facing. It may identify repeated blocks,
route/reuse decisions, late evidence gaps, expensive recovery, checks that can
move earlier, and recurring overrides.

Pilot order remains exact-reuse rejection reasons, then cost/missingness, then
repair-pattern hypotheses after multiple independent plans, lineages, time
separation, and a counterexample. Deterministic classification and
non-authorizing LLM explanation are allowed. It cannot infer causal truth from
raw logs, modify Skills, update baselines, inject production advice, or turn
Catalog projections into memory authority. Sample sufficiency comes from real
TC-D2 cohorts, not a fixed number in this brief.

## 11. TC-D6: Version Governance And Git Rollback

TC-D6 governs one explicit delta to an existing core Skill. It binds Skill and
evaluation deltas, runs accepted evaluation, records maintainer disposition
append-only, publishes by explicit command, retains the prior stable Git
identity, and performs tested rollback without deleting candidate history.

It cannot automatically create/delete/merge/split Skills, promote candidates,
rewrite evidence, replace maintainer judgment, or use Catalog projections as
governance authority. Git identity alone is not a release decision. Rollback
must prove restored consumer behavior, not only a ref or configuration change.

## 12. Cross-Roadmap Acceptance Rules

1. Lifecycle authority and completion remain local to each directory.
2. Producer evidence remains producer-owned and history is append-only.
3. Derived evaluation, review, catalog, and replay outputs are non-authorizing.
4. Requirements have bidirectional exact cover to assertions, commands, tests,
   and current runtime evidence.
5. Behavioral acceptance requires real execution and an observable failure.
6. Every fixed defect binds a regression or a semantic-coverage justification.
7. Every candidate has a tested disable or rollback path.
8. Missing or stale data cannot become success.
9. Current Skills and Accepted ADRs supersede historical protocol details.
10. Phase service or sandbox changes stop this roadmap work and require separate
    authorization.

## 13. Evolution Decisions

Retained: independent directory ownership, pull-only cataloging, Skill plus
evaluation deltas, observable metrics before inferred metrics, four evaluation
sets, hard gates plus Pareto and maintainer judgment, bounded shadows,
Git-backed rollback, and no autonomous SkillOS or presumed RL roadmap.

Updated: E0 is `implementation-authorized`; D1 is a repair target; live inputs
use Skill-input v2; lifecycle functions replace frozen Skill-name lists;
context experiments use typed roles; rollback requires restored behavior.

Removed or deferred: the one-time instruction to create only D1; D1 detailed
requirements; fixed 2026-08 commits, machine paths, state narratives, and
reading checklists; metrics without label provenance; fixed mode names and
unsupported speculative adapters; general Experience Memory/Curator platforms,
autonomous promotion, percentage canaries, and a committed RL directory.

## 14. Next Planning Step

The immediate planning input is `docs/know-tc-d1-rebuild.md`. E0 and D2-D6 stay
reserved. After D1 receives fresh independent review and Acceptance, revalidate
the existing E0 directory against current main. Only after both dependencies
pass should a new source review decide whether TC-D2 is ready for PRD creation.
