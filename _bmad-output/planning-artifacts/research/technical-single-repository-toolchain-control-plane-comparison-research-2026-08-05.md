---
stepsCompleted: [1, 2, 3, 4, 5, 6]
inputDocuments: []
workflowType: 'research'
lastStep: 6
research_type: 'technical'
research_topic: 'Single-repository Toolchain Control Plane comparison: Ji Mu Yun, BMAD, Superpowers, OpenSpec, and Hermes'
research_goals: 'Assess whether Ji Mu Yun reaches high quality after TC-D1, revised 7-12, and 7-31 complete; compare only single-repository planning, execution, verification, review, evidence, recovery, lifecycle, and governance capabilities; exclude reuse, ecosystem, installation, community, and popularity.'
user_name: 'Administrator'
date: '2026-08-05'
web_research_enabled: true
source_verification: true
---

# Research Report: Single-Repository Toolchain Control Plane Comparison

**Date:** 2026-08-05
**Author:** Administrator
**Research Type:** Technical

---

## Research Overview

This report compares the single-repository Toolchain Control Plane of Ji Mu
Yun with BMAD-METHOD, Superpowers, OpenSpec, and Hermes Agent. It deliberately
excludes reuse, installation, ecosystem breadth, community size, popularity,
and multi-maintainer governance. The assessment is limited to the mechanisms
that plan, execute, verify, review, repair, record, recover, and evolve work in
one repository under an AI-led, single-maintainer operating model.

The Ji Mu Yun score is a conditional forecast, not a claim about the current
branch: TC-D1, the revised 7-12 plan, and the repaired and revalidated 7-31 plan
must each reach independently replayable `acceptance-passed` state. Under that
condition, Ji Mu Yun scores **89.3/100** and enters the high-quality first tier,
ahead of BMAD (**82.7**), Superpowers (**81.7**), OpenSpec (**72.6**), and Hermes
(**70.8**) on this deliberately narrow evaluation lens. Differences below
three points remain the same practical tier.

The result is driven by typed lifecycle ownership, candidate identity,
independent P0/P1 verification, bounded semantic review, deterministic closure,
and append-only evidence. The main limitations are protocol complexity,
operator ergonomics, and the absence of TC-D2's accepted quality baseline.
See [Research Synthesis](#research-synthesis) for the executive conclusion,
decision guidance, limitations, and next steps.

## Technical Research Scope Confirmation

**Research Topic:** Single-repository Toolchain Control Plane comparison among
Ji Mu Yun, BMAD, Superpowers, OpenSpec, and Hermes.

**Research Goals:** Assess the hypothetical Ji Mu Yun state after TC-D1, the
revised 7-12 plan, and the 7-31 Evidence Catalog are all implementation- and
acceptance-complete. Compare only in-repository planning, execution,
verification, review, evidence, recovery, lifecycle, and governance. Exclude
cross-repository reuse, installation, ecosystem, community, and popularity.

**Technical Research Scope:**

- Architecture Analysis - single-repository control-plane ownership and boundaries.
- Implementation Approaches - plan-to-code workflow and deterministic enforcement.
- Technology Stack - only where it changes control-plane behavior.
- Integration Patterns - agent, command, review, evidence, and lifecycle integration.
- Performance Considerations - bounded review cost and operational convergence.

**Research Methodology:**

- Current public GitHub data with source verification.
- Primary project documentation and repository contents preferred over commentary.
- Multi-source validation for critical comparative claims.
- Explicit confidence levels and no score for reuse or ecosystem quality.

**Scope Confirmed:** 2026-08-05

## Technology Stack Analysis

### Comparison Type Boundary

The five systems do not all occupy the same product category. Ji Mu Yun,
BMAD, Superpowers, and OpenSpec primarily install or operate repository-local
delivery methods. Hermes Agent is primarily a persistent general-purpose agent
runtime with tools, sessions, memory, gateways, and multiple execution
backends. The later score therefore counts only behavior that directly
controls work inside one repository; breadth outside that boundary receives no
credit.

Repository metadata was checked on 2026-08-05. Current implementation-language
signals were JavaScript/Python for BMAD, Shell/JavaScript for Superpowers,
TypeScript for OpenSpec, and Python/TypeScript for Hermes. Star counts were
used only to confirm the intended high-visibility repositories and are excluded
from scoring.

_Sources: [BMAD repository](https://github.com/bmad-code-org/BMAD-METHOD),
[Superpowers repository](https://github.com/obra/superpowers),
[OpenSpec repository](https://github.com/Fission-AI/OpenSpec),
[Hermes Agent repository](https://github.com/NousResearch/hermes-agent)_

### Ji Mu Yun Hypothetical Control Plane

The Toolchain Control Plane is file-native and deliberately narrow. Markdown
Skills and plans carry human/agent instructions; Python CLIs and validators
enforce behavior; JSON schemas and typed JSON sidecars carry lifecycle,
identity, routing, review, and acceptance facts; Git commits, trees, diffs, and
content hashes establish candidate identity. Codex CLI processes are explicit
execution dependencies rather than hidden provider dispatch.

Under the stated hypothesis, TC-D1 adds portable Skill-validator resolution,
historical replay, and evaluation seeds; revised 7-12 adds bounded review
re-entry recommendations, cost-calibration governance, and thin high-risk
routing; 7-31 adds pull-only producer adapters, immutable Evidence Catalog
generations, Current/LKG publication, bounded queries, and rebuild/restore.
The evidence store remains append-only files and immutable generations rather
than a service database. This maximizes local inspectability and fail-closed
replay, at the cost of a larger custom Python/JSON contract surface.

_Sources: `docs/know.md`,
`execution-plans/2026-07-12-llm-review-evidence-gate-hardening/00-index.md`,
`execution-plans/2026-07-31-toolchain-workflow-evidence-catalog-v1/00-index.md`,
and `.agents/skills/run-phase-bootstrap-review/SKILL.md`._

### BMAD-METHOD

BMAD 6.10 uses Node.js 20.12+ as its installer and framework toolchain, with a
substantial JavaScript codebase and targeted Python utilities. Its repository
uses Markdown/YAML/TOML-style declarative workflow and Skill content, a CLI
installer, deterministic Skill/reference validators, and a mixed Node/Python
test suite. Its strength is a broad structured development method spanning
analysis, planning, architecture, stories, implementation, review, and QA.

For single-repository control, BMAD artifacts and workflow frontmatter provide
continuity, while validators check package and reference integrity. Its core
stack is less centered on hash-bound run evidence and immutable lifecycle
generations than the hypothetical Ji Mu Yun state; much of the workflow
contract is executed through agent instructions and generated artifacts.

_Sources: [BMAD package manifest](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/package.json),
[BMAD README](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/README.md),
[BMAD Skill validator](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/tools/validate-skills.js)_

### Superpowers

Superpowers 6.x is technically lightweight: Markdown Skills are the primary
method, with Shell and JavaScript integration, Git worktrees for isolated
implementation, repository-local `.superpowers/sdd/` scratch state, and tests
for Skills and platform adapters. Its pipeline strongly emphasizes design
before implementation, small implementation plans, TDD, systematic debugging,
subagent-driven execution, review, and branch completion.

That minimal stack is an advantage for legibility and low operational burden.
For this comparison it also establishes a ceiling: Superpowers provides strong
behavioral discipline but not an equivalently rich typed evidence catalog,
formal multi-state acceptance authority, lineage replay, or Current/LKG
publication layer.

_Sources: [Superpowers README](https://github.com/obra/superpowers/blob/main/README.md),
[Superpowers release notes](https://github.com/obra/superpowers/blob/main/RELEASE-NOTES.md),
[Superpowers package manifest](https://github.com/obra/superpowers/blob/main/package.json)_

### OpenSpec

OpenSpec 1.7 is the most directly comparable compact control-plane
implementation. It uses TypeScript 6, Node.js 20.19+, Commander, YAML, Zod,
and Vitest. Repository state is stored under `openspec/`: current
specifications, isolated change directories, archived changes, configuration,
and an artifact dependency graph. Its CLI exposes machine-readable status and
instructions, validation, apply, verify, sync, archive, and profile/drift
operations.

OpenSpec's TypeScript/Zod stack gives it a cohesive typed CLI and a smaller
operational surface than Ji Mu Yun. Its lifecycle is intentionally fluid and
artifact-driven rather than a strict evidence-custody and independent-review
state machine. That distinction will matter more than language choice in the
final score.

_Sources: [OpenSpec package manifest](https://github.com/Fission-AI/OpenSpec/blob/main/package.json),
[OpenSpec README](https://github.com/Fission-AI/OpenSpec/blob/main/README.md),
[OpenSpec CLI documentation](https://github.com/Fission-AI/OpenSpec/blob/main/docs/cli.md)_

### Hermes Agent

Hermes Agent is a Python 3.11-3.13 runtime with a large Python core and
TypeScript user-interface surface. It provides an agent loop, dynamic tool
registry, persistent sessions and memory, command approval/security controls,
subagents, skills, messaging gateways, MCP/ACP integration, and local,
container, SSH, or cloud execution backends. Pytest and Ruff are present in
its development toolchain.

This is the broadest runtime platform in the set, but persistent memory,
messaging, voice, and remote environments do not automatically become
single-repository delivery governance. Hermes receives credit later for tool
execution, security, recovery, and agent continuity only where those
capabilities bind repository work to requirements and observable validation.

_Sources: [Hermes pyproject](https://github.com/NousResearch/hermes-agent/blob/main/pyproject.toml),
[Hermes README](https://github.com/NousResearch/hermes-agent/blob/main/README.md),
[Hermes security documentation](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/security.md)_

### Storage And Execution Comparison

| System | Repository control artifacts | Deterministic enforcement | Execution isolation/runtime |
| --- | --- | --- | --- |
| Ji Mu Yun, hypothetical | Markdown + typed JSON + schemas + Git hashes + immutable generations/Current/LKG | Python validators, registered commands, replay, fail-closed lifecycle gates | Codex subprocess contracts, bounded workspaces and explicit evidence roots |
| BMAD | Markdown/YAML/TOML artifacts and workflow frontmatter | JS/Python validators and workflow-specific tests | Primarily host coding-agent execution |
| Superpowers | Markdown Skills, design/plans, Git branches/worktrees, local SDD scratch state | Skill protocols, tests, TDD and review checkpoints | Git worktrees and subagent task isolation |
| OpenSpec | Specs, change directories, archive, YAML config, artifact graph | TypeScript/Zod CLI, validation, status/instruction graph, Vitest | Host coding-agent execution with tool adapters |
| Hermes | Config, sessions, memory, skills, task/runtime state | Python runtime guards, approvals, tests and tool registry | Local, Docker, SSH and cloud backends plus gateways |

No system receives points merely for using a database or cloud backend. For a
single trusted maintainer, a replayable file/Git evidence model can be stronger
than a service datastore when authority, content identity, and recovery are
explicit.

### Technology Adoption Findings

Three shared trends are visible: Markdown Skills are becoming a common agent
instruction boundary; machine-readable CLI state is increasingly used to keep
agents grounded; and Git/file-native artifacts remain the dominant local
handoff mechanism. Ji Mu Yun's distinguishing technical bet is not a novel
language or runtime. It is the unusually deep combination of content identity,
typed lifecycle authority, independent review evidence, bounded replay, and
derived immutable catalogs inside one repository.

Confidence in this technology-stack characterization is **0.92**. The main
limitation is that public framework behavior can evolve faster than README and
indexed documentation, so final scoring will prefer checked source contracts
over marketing descriptions.

## Integration Patterns Analysis

### Evaluation Lens

For a repository Toolchain Control Plane, the relevant integration is not
REST, GraphQL, or a service mesh. It is the protocol connecting intent,
planning, implementation, verification, review, acceptance, recovery, and
history. A strong integration must answer four questions:

1. What exact artifact is handed to the next stage?
2. Can the consumer verify its identity and freshness without trusting prose?
3. Which component may publish the next lifecycle state?
4. Can interruption or failure resume without rewriting historical evidence?

### Ji Mu Yun: Typed Producer/Consumer Chain

Under the hypothesis, the control plane forms this repository-local chain:

```text
source intent
  -> VDD plan and frozen knowledge/baseline
  -> Quick Dev implementation slices and current terminal validation
  -> Refactor Acceptance candidate/requirement/command closure
  -> optional Bootstrap semantic review or exact validated-envelope reuse
  -> acceptance lifecycle decision
  -> pull-only Evidence Catalog generation and Current/LKG
```

The integration format is typed JSON plus repository-relative paths, Git and
content hashes, registered commands, schema versions, and append-only
receipts. Producers retain native authority; consumers revalidate rather than
copying authority. Bootstrap cannot publish acceptance, the Catalog cannot
publish review or lifecycle state, and VDD cannot publish implementation or
knowledge generations. This separation is unusually strong for a local agent
workflow.

The cost is protocol density. A schema or binding change can affect several
consumers and demands composition replay. TC-D1 and 7-31 are important because
they turn that density from one-off custom validation into portable replay and
inspectable cross-workflow evidence.

_Sources: `docs/standards/bootstrap-review-control-plane.md`,
`.agents/skills/vdd-execution-plan/SKILL.md`,
`.agents/skills/run-refactor-implementation-acceptance/SKILL.md`, and the
7-31 implementation contract._

### BMAD: Artifact-Guided Workflow Integration

BMAD integrates analysis, planning, architecture, epics/stories, sprint
readiness, Build/Build Auto, code review, and retrospective through generated
project artifacts, Markdown workflows, frontmatter state, Git evidence, and
specialized agents. Its readiness gate checks intent-to-story traceability,
dependencies, architecture/UX gaps, and cross-artifact conflicts. Build Auto
uses explicit states such as `ready-for-dev`, `in-progress`, `in-review`,
`done`, and `blocked`, and reports baseline revision and verification risk.

This is a mature end-to-end artifact handoff. The weaker boundary is
machine-level custody: state and transitions are primarily workflow/frontmatter
contracts, rather than one repository-wide schema family binding every
producer, consumer, command, candidate revision, and lifecycle publisher.
Retrospective Git evidence and acceptance verdicts are meaningful, but they do
not form the same immutable run-envelope and replay protocol as hypothetical
Ji Mu Yun.

_Sources: [BMAD workflow map](https://github.com/bmad-code-org/BMAD-METHOD/blob/05e295f48e9176de4e457204325b0444ab185a0f/docs/reference/workflow-map.md),
[BMAD readiness gate](https://github.com/bmad-code-org/BMAD-METHOD/blob/05e295f48e9176de4e457204325b0444ab185a0f/src/bmm-skills/plan/bmad-sprint-planning/references/readiness-gate.md),
[BMAD Build Auto](https://github.com/bmad-code-org/BMAD-METHOD/blob/05e295f48e9176de4e457204325b0444ab185a0f/docs/reference/build-auto.md),
[BMAD retrospective evidence](https://github.com/bmad-code-org/BMAD-METHOD/blob/05e295f48e9176de4e457204325b0444ab185a0f/src/bmm-skills/ship/bmad-retrospective/references/evidence-gathering.md)_

### Superpowers: Task-Oriented Human-Readable Protocol

Superpowers has a highly ergonomic pipeline: brainstorming and design
approval, detailed implementation plans, isolated worktrees, fresh task
implementers, task review, strict TDD, final branch review, and completion
verification. Its SDD workspace stores task briefs, implementer reports,
review packages, fix rounds, progress ledgers, and commits. Reviewers are told
to inspect real code rather than trust implementer summaries.

The protocol is strong as agent behavior and development practice. It is less
strong as a machine authority graph. The progress ledger is controller-written
text under git-ignored scratch state and is removed after clean final review;
Git history becomes the durable record. Reviewer read-only behavior is a prompt
contract rather than an access-proof and sandbox contract. There is no
equivalent unified requirements/state/command registry schema, independent
verification envelope, or immutable evidence generation.

_Sources: [Superpowers SDD workflow](https://github.com/obra/superpowers/blob/44c9b2d6e889982ac18c27d05a19fefe335194e1/skills/subagent-driven-development/SKILL.md),
[worktree protocol](https://github.com/obra/superpowers/blob/44c9b2d6e889982ac18c27d05a19fefe335194e1/skills/using-git-worktrees/SKILL.md),
[review package](https://github.com/obra/superpowers/blob/44c9b2d6e889982ac18c27d05a19fefe335194e1/skills/subagent-driven-development/scripts/review-package)_

### OpenSpec: Artifact Graph And Semantic Delta Integration

OpenSpec cleanly separates current truth in `openspec/specs/` from proposed
changes in `openspec/changes/`. A YAML/Zod artifact graph defines dependencies
among proposal, delta specifications, design, and tasks. Agents query
`status --json` and `instructions --json`, and archive semantically merges
deltas into current specifications. This is the most cohesive compact
machine-readable integration in the comparison.

Its boundary stops earlier than Ji Mu Yun's. Artifact completion is currently
based on output-file presence, not proof that implementation behavior passed.
`/opsx:verify` directs an agent to assess completeness, correctness, and
coherence using searches and inference; it is not a deterministic CLI
implementation-acceptance gate. Archive can proceed after warnings and user
confirmation when artifacts or tasks remain incomplete. Therefore OpenSpec's
specification integration is stronger than its review/evidence integration.

_Sources: [OpenSpec artifact graph](https://github.com/Fission-AI/OpenSpec/blob/59bfb27a7607ebde62959a9dcbc2f563662c04ad/schemas/spec-driven/schema.yaml),
[artifact state](https://github.com/Fission-AI/OpenSpec/blob/59bfb27a7607ebde62959a9dcbc2f563662c04ad/src/core/artifact-graph/state.ts),
[validation CLI](https://github.com/Fission-AI/OpenSpec/blob/59bfb27a7607ebde62959a9dcbc2f563662c04ad/src/commands/validate.ts),
[verify workflow](https://github.com/Fission-AI/OpenSpec/blob/59bfb27a7607ebde62959a9dcbc2f563662c04ad/src/core/templates/workflows/verify-change.ts)_

### Hermes: Runtime Tool And Environment Integration

Hermes integrates an agent loop with a dynamic tool registry, persistent
sessions and memory, subagents, MCP/ACP, messaging gateways, and multiple
execution environments. Its security integration includes dangerous-command
approval modes, file-write restrictions, container isolation, credential
filtering for MCP subprocesses, and cross-session isolation.

These are strong runtime and interoperability capabilities. Within the scoring
boundary, however, Hermes does not automatically connect a repository
requirement inventory to a candidate manifest, registered terminal predicate,
independent review closure, acceptance publisher, and immutable cross-run
catalog. Its extensibility is broader; its repository delivery protocol is
less prescriptive.

_Sources: [Hermes security model](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/security.md),
[Hermes configuration](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/configuration.md),
[Hermes MCP guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/guides/use-mcp-with-hermes.md)_

### Cross-System Protocol Comparison

| Capability | Ji Mu Yun, hypothetical | BMAD | Superpowers | OpenSpec | Hermes |
| --- | --- | --- | --- | --- | --- |
| Machine-readable plan/status | Strong typed plan/lifecycle artifacts | Moderate-strong frontmatter/artifacts | Limited text plans/ledger | Strong artifact graph/JSON status | Runtime/task state, not delivery-specific |
| Candidate identity | Git/content manifests and deletion bindings | Git baseline/evidence in selected workflows | Worktree and commits | Change directory identity | Workspace/session dependent |
| Deterministic implementation acceptance | Registered terminal predicates plus Acceptance | Workflow-specific validation and verdicts | Fresh tests and completion verification | Spec validation strong; implementation verify agent-led | General tool/test execution |
| Review isolation and authority | Separate discovery, verifier, consumer, lifecycle owners | Layered agents and triage | Fresh reviewers, prompt-level read-only | Agent verify, no equivalent independent envelope | Subagents/approvals, no delivery-specific review protocol |
| Durable recovery | Append-only evidence, lineage, exact replay, LKG | Artifact/frontmatter/Git continuity | Scratch ledger plus Git recovery | Change/archive artifacts | Persistent sessions/memory/runtime recovery |
| Cross-run evidence query | Pull-only native adapters and immutable Catalog | Retrospective evidence gathering | No durable run catalog | Archive/spec browsing | Session/memory search, not formal delivery evidence |

### Integration Assessment

The hypothetical Ji Mu Yun state has the strongest repository-local authority
and evidence integration, while BMAD has the broadest mature delivery workflow,
Superpowers has the best task-level developer loop, OpenSpec has the cleanest
compact spec graph, and Hermes has the broadest runtime interoperability.

Confidence is **0.89**. Positive capabilities are backed by current official
source. Confidence is lower for absence claims because public repositories may
contain experimental branches or undocumented features; the comparison only
credits behavior visible in current mainline contracts.

## Architectural Patterns And Design

### System Architecture Patterns

The systems fall into four architectural families:

- **Formal local control plane:** hypothetical Ji Mu Yun separates lifecycle
  publishers, producers, consumers, validators, review roles, and derived
  evidence projections. State transitions are explicit and fail closed.
- **Artifact-guided method framework:** BMAD composes specialized agents and
  workflows around durable planning and delivery artifacts.
- **Behavioral development protocol:** Superpowers uses concise Skills,
  worktree isolation, fresh task agents, review loops, and Git as the durable
  backbone.
- **Artifact graph:** OpenSpec represents specification change as a dependency
  graph and semantic delta that eventually merges into current truth.
- **Persistent agent runtime:** Hermes organizes tools, sessions, memory,
  gateways, and execution environments around a continuously operating agent.

No family is universally superior. For one repository maintained by one
trusted person and AI, the formal control-plane pattern is strongest when a
wrong lifecycle decision is expensive; the behavioral protocol is strongest
when iteration speed and low ceremony dominate.

### Design Principles And Authority

Hypothetical Ji Mu Yun most closely follows separation of authority and
content-addressed event/evidence patterns. VDD may publish plan readiness but
not implementation; Quick Dev may publish implementation completion but not
acceptance; Bootstrap produces supplemental semantic review evidence but not
acceptance; Refactor Acceptance owns acceptance; the Catalog indexes native
evidence but owns no producer state. Each boundary narrows accidental
self-approval.

BMAD and Superpowers also separate roles, but more of the separation is
instructional. BMAD's layered review agents and Superpowers' fresh implementer
and reviewer sessions reduce correlated error. Their state is easier to read
and operate, but a malformed or stale handoff is less consistently rejected by
one machine contract.

OpenSpec explicitly favors actions over a phase-locked state machine. This is
excellent for fluid specification work, but less suited to proving that a
specific implementation candidate crossed independent acceptance. Hermes
separates the agent, tools, environments, sessions, and gateways; its
separation protects runtime execution rather than delivery-state authority.

_Sources: [BMAD review configuration](https://github.com/bmad-code-org/BMAD-METHOD/blob/05e295f48e9176de4e457204325b0444ab185a0f/src/bmm-skills/ship/bmad-code-review/customize.toml),
[Superpowers task reviewer](https://github.com/obra/superpowers/blob/44c9b2d6e889982ac18c27d05a19fefe335194e1/skills/subagent-driven-development/task-reviewer-prompt.md),
[OpenSpec concepts](https://github.com/Fission-AI/OpenSpec/blob/59bfb27a7607ebde62959a9dcbc2f563662c04ad/docs/concepts.md),
[Hermes architecture entry](https://github.com/NousResearch/hermes-agent/blob/main/README.md)_

### Scalability And Performance Patterns

For this comparison, scale means growing requirements, plans, runs, findings,
contexts, and evidence inside one repository.

- Ji Mu Yun scales evidence through producer allowlists, immutable generations,
  bounded queries, Current/LKG, and content identity. Revised 7-12 calibrates
  review cost and prevents later full finding mode without a typed trigger and
  confirmation. Its risk is validation amplification: broad schema or policy
  changes can require expensive composition and terminal replay.
- BMAD scales human/agent comprehension through phase artifacts, stories,
  navigation, readiness checks, and module boundaries. Its current Blind
  Hunter instruction requiring a minimum issue count creates avoidable review
  pressure and makes cost less predictable.
- Superpowers scales execution through small tasks, fresh subagents, model
  tiers, scoped re-review, and a five-round breaker. It is operationally
  efficient but lacks a durable cross-run cost/yield baseline in the same repo.
- OpenSpec's DAG and JSON status make dependency queries cheap and predictable.
  Its lighter verification is correspondingly less expensive and less
  authoritative.
- Hermes scales runtime context through sessions, memory, toolsets, and context
  management, but that does not solve repository acceptance-evidence growth.

_Sources: [BMAD Blind Hunter configuration](https://github.com/bmad-code-org/BMAD-METHOD/blob/05e295f48e9176de4e457204325b0444ab185a0f/src/bmm-skills/ship/bmad-code-review/customize.toml),
[Superpowers repair breaker and model routing](https://github.com/obra/superpowers/blob/44c9b2d6e889982ac18c27d05a19fefe335194e1/skills/subagent-driven-development/SKILL.md),
[OpenSpec workflow status](https://github.com/Fission-AI/OpenSpec/blob/59bfb27a7607ebde62959a9dcbc2f563662c04ad/src/commands/workflow/status.ts)_

### Review And Acceptance Architecture

BMAD, Superpowers, and hypothetical Ji Mu Yun all use multiple perspectives,
but their closure models differ materially.

BMAD's review is mature and adversarial: multiple layers, source reread,
deduplication, independent checking, and triage. Its default Blind Hunter is
still explicitly finding-driven, which can bias cost and finding volume.
Superpowers uses a strong task-level double verdict and final branch review,
with current tests required before completion. It optimizes for engineering
behavior rather than durable formal evidence.

Ji Mu Yun adds typed finding gates, independent P0/P1 verification,
risk-dependent model/effort routing, stable lineage, bounded semantic rounds,
focused repair verification, deterministic closure, exact finalized-envelope
reuse, and explicit user confirmation for later complete finding mode. If the
three assumed directories pass acceptance, it also gains portable replay,
evaluation seeds, baseline-informed re-entry advice, cost-calibration
promotion/rollback, and cross-run Catalog inspection. This is the strongest
formal review architecture in the comparison, but only if its many contracts
remain internally consistent and usable.

OpenSpec verifies specification structure deterministically and implementation
semantics heuristically through its agent workflow. Hermes can run reviewers
or tests as tools but does not prescribe an equivalent acceptance architecture.

### Security Architecture Patterns

Hermes has the broadest general runtime security surface: dangerous-command
approval, write restrictions, container isolation, MCP credential filtering,
session isolation, and backend validation. Ji Mu Yun has the strongest
review-specific custody model: isolated review roles, explicit access proof,
bounded Artifact Views, candidate manifests, process events, protected
authority roots, and fail-closed stale evidence.

Superpowers uses Git worktrees and prompt-level reviewer read-only rules. BMAD
uses role separation and workflow boundaries. OpenSpec uses bounded project
directories and validation but does not present a comparable reviewer custody
protocol. Because the scenario assumes one trusted maintainer and excludes
external injection and multi-writer concurrency, no score is awarded merely
for broader tenant or collaboration controls.

_Source: [Hermes security model](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/security.md)_

### Data And Recovery Architecture

All five systems are substantially file-native, but their durability models
differ:

- Ji Mu Yun: append-only run evidence, hash-bound content manifests, lineage,
  immutable Catalog generations, Current/LKG, and rebuild/restore.
- BMAD: project artifacts, workflow frontmatter, Git evidence, sprint state,
  retrospective inventory, and acceptance verdict.
- Superpowers: plan-scoped ignored scratch ledger during work, then Git history
  after clean completion; `git clean -fdx` can remove the live ledger.
- OpenSpec: current specs, active changes, task state, and dated archive.
- Hermes: persistent sessions, memory, configuration, and runtime state.

Ji Mu Yun's design has the best audit and replay properties. Superpowers has
the simplest operating model. OpenSpec has the cleanest specification-state
model. BMAD has the richest human-readable project history. Hermes has the
richest conversational continuity.

### Deployment And Operations Architecture

Deployment breadth is out of score. The control-plane comparison credits only
local operations that affect repository correctness. Consequently Hermes does
not gain points merely for Docker, SSH, cloud, messaging, or desktop support,
and OpenSpec/BMAD/Superpowers do not lose points for being primarily local
coding-agent methods.

The central operations question is recovery cost. Ji Mu Yun can recover the
most exact state but demands the most operator knowledge. Superpowers is easy
to run but may reconstruct lost scratch state from Git. BMAD sits between
those extremes. OpenSpec is easy to inspect and archive but cannot reconstruct
formal semantic review evidence it never captured.

### Scoring Architecture

The final score uses ten dimensions totaling 100 points. Reuse, ecosystem,
installation, popularity, number of supported IDEs/models, and multi-tenant
features receive zero weight.

| Dimension | Weight | What earns credit |
| --- | ---: | --- |
| Requirements and planning | 12 | Stable intent, traceability, dependencies, actionable plan |
| Implementation orchestration and TDD | 12 | Bounded execution, isolation, tests, current completion evidence |
| Deterministic validation and acceptance | 14 | Machine predicates, requirement closure, independent acceptance state |
| Review and repair governance | 12 | Review quality, verification, bounded loops, cost-aware re-entry |
| Evidence and provenance | 14 | Candidate identity, durable evidence, traceability, query/replay |
| Lifecycle and recovery | 10 | Explicit states, ownership, resume, rollback/LKG, fail-closed behavior |
| Knowledge and context integrity | 6 | Fresh bounded context, source identity, stale rejection |
| Model, tool, and execution security | 6 | Explicit routing, isolation, approvals, custody appropriate to repo risk |
| Self-evaluation and evolution governance | 7 | Regression/evaluation delta, baseline comparison, controlled promotion |
| Operational ergonomics and maintainability | 7 | Low ceremony, comprehensibility, bounded custom complexity |

This weighting deliberately prevents formalism from winning by volume. A
large protocol surface loses points when it increases maintenance burden
without additional observable safety. Conversely, a simple method loses points
only when a missing machine boundary permits false completion, stale evidence,
or unrecoverable state.

Architectural-analysis confidence is **0.88**. Positive architectural facts
are well supported; the hypothetical Ji Mu Yun score remains conditional on
all three directories reaching `acceptance-passed`, not merely having plan or
implementation state.

## Implementation Approaches And Technology Adoption

### Adoption Strategy For Ji Mu Yun

The recommended adoption is sequential rather than a big-bang control-plane
release:

1. Complete TC-D1 and its independent acceptance first. This establishes a
   repository-owned portable Skill validator/replay entrypoint and preserves
   the three 8-01 repair families as non-authorizing evaluation seeds.
2. Complete revised 7-12 next. This adds evidence-informed later finding-mode
   recommendations, controlled cost-calibration promotion/rollback, entrypoint
   census, and thin delegation only after a high-risk caller selects complete
   semantic review.
3. Repair/revalidate, implement, and accept 7-31 last. Catalog adapters then
   consume stable producer-native formats, reducing repeated adapter repair.

Activation should remain capability-by-capability. No feature becomes current
because its plan or implementation exists; each waits for current terminal
validation and independent Acceptance.

### Development Workflows And Tooling

The hypothetical Ji Mu Yun workflow should retain four first-level Toolchain
Skills rather than introduce another orchestration layer. VDD owns complete
plan creation/repair, Quick Dev owns implementation slices, Bootstrap owns
semantic review evidence, and Refactor Acceptance owns the final acceptance
lifecycle. The Evidence Catalog is a derived read model, not a fifth lifecycle
owner.

Compared with the other systems:

- BMAD remains the best reference for broad product-development artifact flow
  and readiness checks.
- Superpowers remains the best reference for concise task plans, strict TDD,
  fresh completion evidence, and low-friction repair loops.
- OpenSpec remains the best reference for a compact artifact DAG and dynamic
  machine-readable instructions.
- Hermes remains the best reference for runtime tool security, execution
  environments, and CI/supply-chain automation.

Ji Mu Yun should absorb practices, not duplicate frameworks or modify
installer-managed BMAD/GDS files.

### Testing And Quality Assurance

The strongest current patterns are complementary:

- Superpowers requires RED, observed failure, minimal GREEN, full current
  verification, and no completion claim based on stale results.
- BMAD combines readiness, layered review, source reread, triage, Git evidence,
  and retrospective acceptance.
- OpenSpec validates schema, artifact dependencies, normative requirement
  syntax, and semantic deltas deterministically.
- Hermes uses sharded isolated Pytest execution, locked dependencies,
  credential-cleared CI jobs, and targeted supply-chain audits.
- Ji Mu Yun combines deterministic terminal predicates with typed acceptance,
  independent P0/P1 verification, bounded semantic review, content custody,
  and replay.

The remaining Ji Mu Yun gap after the three assumed directories is TC-D2:
evaluation seeds are not yet a quality baseline. Stable/candidate comparison,
label provenance, Anchor/Frontier/Challenge/Holdout classes, and hard-gate plus
Pareto policy remain future work.

_Sources: [Superpowers TDD](https://github.com/obra/superpowers/blob/44c9b2d6e889982ac18c27d05a19fefe335194e1/skills/test-driven-development/SKILL.md),
[BMAD acceptance verdict](https://github.com/bmad-code-org/BMAD-METHOD/blob/05e295f48e9176de4e457204325b0444ab185a0f/src/bmm-skills/ship/bmad-retrospective/references/acceptance-verdict.md),
[OpenSpec validator](https://github.com/Fission-AI/OpenSpec/blob/59bfb27a7607ebde62959a9dcbc2f563662c04ad/src/core/validation/validator.ts),
[Hermes CI](https://github.com/NousResearch/hermes-agent/blob/af8d698b/.github/workflows/ci.yml)_

### Operations And Recovery

The implementation should preserve append-only failure evidence, immutable
generations, Current/LKG separation, and explicit restore. Catalog publication
must remain independent of consumer-side stale recovery. A stale consumer may
route to maintenance but cannot authorize global publication.

Operationally, the largest risk is not data loss but protocol drift: one Skill,
schema, route policy, or validator changes while a direct consumer still binds
the old shape. TC-D1 portable replay and 7-31 producer-specific adapters reduce
this risk, but terminal composition tests remain necessary for shared
contracts.

### Maintainer Skills And Operating Model

The target remains AI-led and single-maintainer. It does not need signer
quorums, multi-writer locks beyond real process mutation hazards, or governance
for hostile external requirement injection. It does require the maintainer to
understand lifecycle ownership, the distinction between native and derived
evidence, stale/fresh candidate identity, and when a semantic review is worth
its cost.

The system should expose compact read-only inspection commands so ordinary
operation does not require manual JSON archaeology. This is where Ji Mu Yun
still trails Superpowers and OpenSpec ergonomically.

### Cost Optimization

Cost control has four layers:

1. deterministic validation before semantic review;
2. complete finding discovery automatically only in Round 1;
3. focused verification or deterministic closure after bounded repairs;
4. later full finding mode only with typed trigger, evidence-informed
   recommendation, explicit confirmation, and calibrated expected cost.

Historical baselines and Catalog queries remain advisory. A similar prior run
or clean baseline cannot establish current correctness. Revised 7-12 improves
the decision to spend review cost; TC-D2 is still required before claiming a
cross-Skill quality/cost optimum.

### Risk Assessment

| Risk after the three completions | Severity | Mitigation |
| --- | --- | --- |
| Protocol/schema sprawl raises maintenance cost | P1 architectural | Keep four core Skills, delete duplicated owners, require composition replay only for shared contracts |
| Formal controls reduce ordinary-task throughput | P1 operational | Preserve low-risk lightweight routes; high-risk routing must not automatically select complete review |
| Catalog is mistaken for lifecycle authority | P1 authority | Pull-only adapters, `authorizes=[]`, producer-native verification, explicit Current/LKG ownership |
| Seeds are mistaken for a quality baseline | P1 evaluation | Keep TC-D1 seeds non-authorizing; reserve baseline publication for TC-D2 |
| Hypothetical score is treated as current fact | P1 governance | Publish the comparison as conditional on three independent `acceptance-passed` states |
| Local custom implementation becomes opaque | P2 maintainability | Add bounded inspect/status commands and concise operator projections rather than more narrative books |

## Comparative Score

Each dimension is scored from 0 to 10 and multiplied by the frozen weight from
the architecture section.

| Dimension | Weight | Ji Mu Yun hypothetical | BMAD | Superpowers | OpenSpec | Hermes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Requirements and planning | 12 | 9.2 | 9.2 | 9.0 | 8.8 | 5.5 |
| Implementation orchestration and TDD | 12 | 8.4 | 8.8 | 9.0 | 7.5 | 7.6 |
| Deterministic validation and acceptance | 14 | 9.4 | 7.8 | 9.5 | 7.6 | 7.0 |
| Review and repair governance | 12 | 9.3 | 8.6 | 9.2 | 6.3 | 5.8 |
| Evidence and provenance | 14 | 9.7 | 8.2 | 6.0 | 5.8 | 6.2 |
| Lifecycle and recovery | 10 | 9.4 | 8.0 | 7.5 | 6.8 | 7.5 |
| Knowledge and context integrity | 6 | 9.2 | 8.5 | 7.2 | 7.8 | 8.2 |
| Model, tool, and execution security | 6 | 9.1 | 6.5 | 6.8 | 6.0 | 9.5 |
| Self-evaluation and evolution governance | 7 | 7.4 | 7.8 | 7.0 | 7.5 | 8.5 |
| Operational ergonomics and maintainability | 7 | 6.7 | 8.4 | 9.3 | 9.1 | 8.0 |
| **Weighted total** | **100** | **89.3** | **82.7** | **81.7** | **72.6** | **70.8** |

### Score Interpretation

- **Ji Mu Yun, 89.3:** high-quality first-tier formal repository control
  plane, strongest in evidence, lifecycle, acceptance, and replay. It loses
  points for complexity and the absence of TC-D2's accepted quality baseline.
- **BMAD, 82.7:** most complete general delivery method and strongest broad
  artifact workflow. Its default review retains a finding-driven bias and its
  cross-stage authority is less uniformly machine-bound.
- **Superpowers, 81.7:** best day-to-day engineering behavior loop, TDD, review,
  and ergonomics. Its durable formal evidence and machine lifecycle are thin.
- **OpenSpec, 72.6:** excellent compact spec/change graph and deterministic
  specification validation. Implementation acceptance and run evidence are
  materially lighter.
- **Hermes, 70.8:** excellent general agent runtime, security, CI, tools, and
  memory. It scores lower because repository specification-to-acceptance
  governance is not its primary architecture.

Score confidence: Ji Mu Yun **0.78** because it is hypothetical; BMAD **0.88**;
Superpowers **0.91**; OpenSpec **0.91**; Hermes **0.80**. The overall ranking
confidence is **0.84**. Differences smaller than three points should be treated
as the same practical tier rather than a decisive ordering.

## Technical Research Recommendations

### Implementation Roadmap

Keep the sequence `TC-D1 -> revised 7-12 -> repaired 7-31`. After all three
pass Acceptance, run one bounded cross-workflow replay and operations exercise
before declaring the high-quality baseline current. Do not immediately start
another broad finding-driven review solely to validate the claim.

### Next Quality Investment

After operational stabilization, TC-D2 is the highest-value next control-plane
directory. It should convert non-authorizing seeds and Catalog observations
into a versioned quality evaluation baseline with label provenance and holdout,
without creating autonomous Skill modification.

### Success Metrics

- every lifecycle claim replays against current candidate bytes;
- no consumer acquires a producer's authority;
- later complete finding-mode frequency and cost decrease without accepted
  P0/P1 escape evidence increasing;
- Catalog rebuild and LKG restore are deterministic;
- ordinary low-risk work remains materially cheaper than high-risk review;
- Skill changes carry an evaluation delta or prove existing coverage;
- operator recovery does not require editing generated historical evidence.

---

<!-- Content will be appended sequentially through research workflow steps -->

## Research Synthesis

### Executive Summary

Assuming TC-D1, revised 7-12, and repaired 7-31 are all implemented and pass
independent acceptance, Ji Mu Yun has a high-quality single-repository
Toolchain Control Plane. It is especially strong where an AI-led repository is
most vulnerable to plausible but ungrounded completion claims: candidate byte
identity, typed producer and consumer authority, replayable evidence,
independent verification, bounded review re-entry, and deterministic lifecycle
closure. These controls form a coherent system rather than a collection of
prompts.

The comparison does not establish universal superiority. BMAD remains the
broadest end-to-end delivery method; Superpowers provides the strongest
day-to-day TDD and task-review ergonomics; OpenSpec has the cleanest compact
artifact graph and specification delta workflow; Hermes has the strongest
general agent runtime and security posture. Ji Mu Yun leads only on the frozen
single-repository control-plane dimensions and weights defined in this report.
Its **89.3** score is conditional and carries **78%** confidence because three
future acceptance outcomes are assumed. Overall rank confidence is **84%**.

The correct next action is therefore not another untriggered high-cost finding
review. Complete the three directories in the order `TC-D1 -> revised 7-12 ->
repaired 7-31`, run one bounded cross-workflow replay and recovery exercise,
then stabilize ordinary use. After operating evidence exists, TC-D2 should
turn evaluation seeds into a versioned quality baseline with label provenance,
Anchor/Frontier/Challenge/Holdout cohorts, and quality-cost Pareto comparison.

**Key findings:**

- Ji Mu Yun's strongest differentiator is evidence authority: lifecycle claims
  bind to current candidate content and cannot be authorized by stale summaries.
- Revised 7-12 makes complete finding mode a typed, evidence-informed exception
  after the first broad review, reducing open-ended review cost without treating
  historical baselines as current correctness proof.
- TC-D1 supplies portable replay and evaluation seeds, but those seeds remain
  non-authorizing until TC-D2 publishes a validated quality baseline.
- Repaired 7-31 supplies an immutable Evidence Catalog with explicit Current/LKG
  behavior while preserving producer-native authority.
- The main remaining engineering risk is protocol drift across Skills, schemas,
  route policies, validators, and direct consumers.
- The main usability gap is compact inspection and status tooling; routine
  operation still demands more protocol knowledge than Superpowers or OpenSpec.

### Table of Contents

1. [Scope and Method](#technical-research-scope-confirmation)
2. [Technology Stack](#technology-stack-analysis)
3. [Integration Patterns](#integration-patterns-analysis)
4. [Architecture and Authority](#architectural-patterns-and-design)
5. [Implementation and Operations](#implementation-approaches-and-technology-adoption)
6. [Comparative Score](#comparative-score)
7. [Recommendations](#technical-research-recommendations)
8. [Strategic Interpretation](#strategic-interpretation)
9. [Implementation Roadmap and Gates](#implementation-roadmap-and-gates)
10. [Future Quality Outlook](#future-quality-outlook)
11. [Methodology and Source Verification](#methodology-and-source-verification)
12. [Limitations and Decision Rules](#limitations-and-decision-rules)

### Strategic Interpretation

#### What the score means

The score indicates that the hypothetical Ji Mu Yun control plane is more
rigorous than the comparison set at preserving the relationship between intent,
candidate content, review, acceptance, and durable evidence. This is a useful
advantage for AI-led maintenance because the dominant failure is often not an
obvious test failure, but an unsupported transition from "the agent reported
success" to "the repository accepted this exact candidate."

The score does not mean every change should enter the full control plane.
Low-risk work still needs a lightweight path. Complete semantic finding review
is justified for the first review of a material change and for later typed
triggers such as accepted evidence escape, candidate identity change, or
material contract drift. Deterministic checks, focused verification, or closure
should handle later rounds when no such trigger exists.

#### Comparative positioning

| System | Best single-repository strength | Principal limit under this lens |
| --- | --- | --- |
| Ji Mu Yun | Evidence-bound lifecycle, acceptance, recovery, and review-cost governance | Protocol complexity and weak operator ergonomics |
| BMAD | Broad artifact-led product delivery workflow | Review remains substantially finding-driven; machine authority is less uniform across stages |
| Superpowers | TDD, task execution, repair loop, and daily usability | Durable provenance and lifecycle evidence are comparatively thin |
| OpenSpec | Compact artifact DAG, spec deltas, and deterministic spec validation | Implementation verification and run-evidence authority are lighter |
| Hermes | General agent runtime, tools, memory, security, and CI | Specification-to-acceptance governance is not the primary architecture |

Ji Mu Yun, BMAD, and Superpowers should be treated as the first practical tier
for this comparison. Ji Mu Yun leads the formal-control subset; BMAD and
Superpowers can still be the better operational choice when breadth or daily
developer flow matters more than immutable evidence and typed lifecycle
authority.

### Implementation Roadmap and Gates

#### Gate 1: TC-D1

Complete portable replay and evaluation seeds first. Acceptance must prove that
the same candidate and envelope can be reconstructed and evaluated without
granting the seeds baseline authority. This creates the measurement substrate
needed by both 7-12 cost governance and later TC-D2 evaluation.

#### Gate 2: Revised 7-12

Implement bounded finding-mode re-entry and cost calibration against accepted
evidence. Acceptance must demonstrate that Round 1 remains broad, subsequent
rounds converge through focused verification or deterministic closure, and a
later complete finding round requires a typed trigger plus explicit approval.
No baseline sample may replace validation of the current candidate.

#### Gate 3: Repaired 7-31

Repair and revalidate the directory before implementation, then deliver the
immutable Evidence Catalog, Current/LKG behavior, producer-specific adapters,
and deterministic rebuild and restore. Acceptance must prove that the Catalog
is query and recovery infrastructure, not a new source of producer lifecycle
authority.

#### Operational qualification

After all three gates pass, run one bounded composition exercise across at
least one representative workflow. Verify candidate replay, Catalog publication,
Current/LKG restoration, focused repair, and terminal acceptance without
rewriting historical evidence. Only then should the hypothetical quality claim
be promoted to a current repository baseline.

### Future Quality Outlook

The next high-value investment is TC-D2, but only after the completed control
plane has produced stable operating samples. TC-D2 should define versioned
quality labels and provenance, separate Anchor, Frontier, Challenge, and
Holdout cohorts, compare quality and cost on a Pareto frontier, and prevent
training or tuning decisions from contaminating holdout evaluation.

TC-D2 should remain advisory to Skill evolution. It may recommend a change and
measure its delta, but it should not autonomously rewrite or publish Skills.
The intended maturity progression is:

`replayable evaluation seeds -> accepted operating samples -> versioned quality baseline -> evidence-informed Skill change -> independent delta evaluation`

In the nearer term, add compact read-only inspection commands and composition
tests for shared protocols. These improve maintainability without creating a
new authority layer or expanding the number of core Skills.

### Methodology and Source Verification

The research used a frozen, weighted scorecard covering requirements and
planning, implementation and TDD, deterministic acceptance, review and repair,
evidence and provenance, lifecycle and recovery, context integrity, execution
security, self-evaluation, and operational ergonomics. Reuse, ecosystem,
installation, popularity, IDE breadth, hostile external injection, and
multi-maintainer governance were excluded before scoring.

Ji Mu Yun was assessed from repository-local plans, standards, Skills, schemas,
validators, and evidence contracts. External systems were checked against
their public primary repositories and pinned implementation snapshots where
the relevant files were available:

- BMAD-METHOD: `main@05e295f`, release line `v6.10.0`.
- Superpowers: `main@44c9b2d`, release line `v6.2.0`.
- OpenSpec: `main@59bfb27`, release line `v1.7.0`.
- Hermes Agent: inspected repository and CI/security snapshot `af8d698b`.

Primary source links and claim-specific citations appear in the Technology
Stack, Integration, Architecture, and Implementation sections above. Critical
comparative claims were checked against workflow definitions, validators,
configuration, or source code rather than relying only on project marketing
text.

### Limitations and Decision Rules

- The Ji Mu Yun result is counterfactual until all three directories reach
  independently replayable `acceptance-passed` state.
- Project implementations evolve; external scores describe the pinned snapshots
  and the frozen comparison lens, not all future releases.
- Hermes belongs to a broader runtime category, so its lower score does not
  imply a weaker general-purpose agent system.
- Numeric precision supports transparent weighting; it does not imply empirical
  accuracy to one decimal place. Treat differences under three points as a tie.
- No benchmark measured wall-clock latency, token cost, defect escape rate, or
  maintainer learning time across identical tasks. Those require TC-D2-style
  controlled samples.
- Baselines and Catalog records inform review routing and evaluation; neither
  can prove the correctness of a current candidate without current validation.

### Final Technical Conclusion

With the three assumed completions, Ji Mu Yun reaches a high-quality
single-repository Toolchain Control Plane and has a defensible lead in formal
evidence, lifecycle, acceptance, and recovery. Its next maturity step is not
more unconditional review. It is to operate the completed system, collect
accepted samples, improve inspection ergonomics, and build TC-D2 as a genuine
quality-and-cost evaluation layer.

**Technical Research Completion Date:** 2026-08-05
**Research Confidence:** High for external architecture comparisons; medium-high
for Ji Mu Yun's conditional score
**Overall Ranking Confidence:** 84%
