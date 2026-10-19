# Package A: Repository Skill Authoring Standard

## FR-1: Standard, contract and deterministic validation entry

Implement one capability-aware authoring standard and a read-only local package
validator. Package A checks package declarations and structure. It never grants
execution permissions, runs a Skill, or establishes runtime security or product
acceptance. Phase's existing isolation/recovery and Quick Dev's current evidence
writers remain their respective authorities.

The following are separate observable obligations; keep distinct Acceptance
assertions even when several use the same implementation owner.

| Intent | Required behavior and independent oracle | Negative/boundary case and failure intent |
| --- | --- | --- |
| A01 | The standard defines one primary responsibility, triggers, non-goals, I/O, dependencies, references, tests, evidence and lifecycle boundaries. A governed fixture missing a required declared section is rejected by the validator. | Remove a required declaration or its referenced section; validation must identify the rule and relative location, not accept headings alone. |
| A02 | The versioned quality contract schema accepts a valid contract, rejects unsupported versions, malformed types, undeclared fields in the owned quality namespace and unresolved references, and records capabilities explicitly. | A typo in a capability or schema version must fail; it must not silently become an empty/disabled capability. |
| A03 | Validate frontmatter, nonempty name/description, canonical package name and its consistency with the declared Skill identity. | Missing/malformed frontmatter, duplicate keys, conflicting name and unsupported frontmatter extension are invalid. Parse safely; YAML/object constructors must never execute. |
| A04 | Enforce fewer than 500 logical lines in SKILL.md, counting frontmatter, blank lines and code blocks; recommend a smaller main file without a second hard gate. | 499 lines pass and 500/501 fail. LF and CRLF have the same count; a final newline does not add an extra logical line. This preserves old SAS-A05 and Package B's below-500 boundary. |
| A05 | Required content moved out of SKILL.md remains reachable through a direct first-level local reference to an existing file and section. | Missing file/anchor, traversal, absolute path or symlink escape is rejected before reading outside the package. Optional remote documentation is not fetched and cannot substitute for required local content. |
| A06 | The public CLI and Python entry return deterministic structured results, correct exit semantics and a bounded list of rule/path/message diagnostics. | Malformed JSON, unreadable/out-of-root target, duplicate keys and unsupported contract versions cannot return pass. Two runs over identical bytes and policy yield equivalent sorted output, without timestamps or environment secrets. |

Production deliverables are:

- `docs/standards/skill-authoring-standard.md`.
- `docs/adr/ADR-0062-repository-skill-authoring-contract.md`, plus its entry in
  `docs/architecture/ADR_INDEX_PHASE.md`. ADR-0060 already belongs to Skill-input
  selection and must not be reused or overwritten. Recheck ADR-0062 availability
  before authoring; a collision requires updating the declared path before RED.
- `scripts/sc/config/skill-authoring-standard.v1.json`.
- `scripts/sc/schemas/skill-quality-contract.v1.schema.json`.
- `scripts/sc/schemas/skill-quality-result.v1.schema.json`.
- `scripts/sc/validate_skill_quality.py`, with a callable `validate_package`
  entry and an argparse-based `main` entry.

The normative schema and policy are the validator's actual inputs, not parallel
unused documentation. Reuse existing repository dependency versions and JSON
validation utilities when suitable. Do not add a model, HTTP request, installer,
new dependency service or automatic execution of package-declared commands.

The per-package quality declaration may be a sidecar such as
`skill-quality.v1.json`. It must coexist with the existing owner-specific
`scripts/skill-contract.json` and `references/skill-input-contract.v1.json`.
Do not repurpose, replace, or change those protocols. Document the versioned
quality namespace, supported frontmatter keys, relative reference rules and
normalization. All semantic fields remain in the quality sidecar or references;
unsupported Skill frontmatter keys must not be introduced.

Public invocation contract (repository root as cwd):

```text
python -B scripts/sc/validate_skill_quality.py --repository-root . --policy scripts/sc/config/skill-authoring-standard.v1.json --skill-root <package-root> --mode strict
```

`python` denotes the active interpreter; Windows users may invoke `py -3 -B`.
No shell string is a machine command contract. Each invocation has a finite
positive timeout assigned by its caller. `validate_package` accepts explicit
repository root, package root, policy and mode and returns the same result shape.
The CLI prints one JSON object and no raw package content. Results use a
versioned schema, package identity, status, ordered diagnostics and
`authorizes: []`. Exit codes are 0/pass, 1/fail (noncompliant package), 2/error
(invalid invocation or unavailable inspection), and 3/legacy (inventory only).
These codes belong only to this validator; do not create a toolchain-wide error
taxonomy. A diagnostic must not echo secret values, absolute host paths or
arbitrary source text. Strict mode never treats legacy or error as success.

## FR-2: Examples, routing, dependencies and operational declarations

| Intent | Required behavior and independent oracle | Negative/boundary case and failure intent |
| --- | --- | --- |
| A07 | Exactly three primary ordered examples cover typical, boundary and error routes; each has nonempty Input and Output tied to distinct declared branch IDs and expected results. Supplemental examples may live in references and do not alter the primary set. | Missing/empty pair, wrong order, duplicate branch, unknown branch or identical normalized Input/Output with different labels fails. |
| A08 | Routing/orchestration Skills have a linked ASCII decision diagram whose declared reachable branch IDs include the three primary example routes. Leaf Skills are explicitly not applicable. | Missing diagram, unresolved branch or false leaf classification with declared routing fails. Do not require a diagram for a real leaf Skill. |
| A09 | Each dependency declares identity, compatible version or repository-owned authority reference, required/optional kind, and deterministic missing/mismatch behavior. | Missing required dependency, incompatible version or unresolved authority yields a typed blocking diagnostic. An optional absence follows its declared fallback, which itself must be resolvable and cannot authorize protected work. |
| A10 | Every public entry declares its accepted input, output, preflight and standalone behavior, including legitimate child dependencies. | A declaration that needs an undeclared caller setup, silently installs a missing child or silently proceeds past a required dependency fails. No global total-entry Skill is introduced. |
| A11 | Complex deterministic checks declare a script entry, test coverage and structured invocation with argv array, bounded timeout, explicit cwd, shell=false and typed result. | String shell command, missing/zero/unbounded timeout, unsafe cwd, missing script/test or untyped result fails static validation. The validator does not execute the supplied command to check it. |
| A12 | FAQ is optional. Every supplied FAQ entry is reached from a declared stable error ID or decision branch, with a resolvable local target. | No FAQ passes. Orphan entry, dead target and unknown error/branch fail; adding an otherwise unused FAQ is not required. |

Use `scripts/sc/skill_quality_examples.py` for bounded parsing and example/branch
checks where separation improves clarity. The main validator must actually
consume it. Package A can mechanically detect missing structure, inconsistent
branch declarations and duplicate examples; it cannot prove the semantic quality
of arbitrary prose. External review evaluates whether the three examples are
materially different and useful. A passing static result must not claim that a
model independently reviewed their meaning. No internal reviewer is required.

Dependencies are resolved from explicit supplied local records. Do not scan all
repositories, select a 'latest successful' log, require publication of the
knowledge base, or turn the new standard into a knowledge-query workflow.

## FR-3: Capability-conditioned safety declarations

Validation here proves the presence and internal consistency of declarations
and local fixtures. It must not claim that a user's prose or a JSON flag enforces
OS isolation, network policy, confirmation or database recovery at runtime.
Existing owning entrypoints enforce those capabilities. Name those owners in
the contract; Package A neither reimplements them nor invokes them.

| Intent | Required behavior and independent oracle | Negative/boundary case and failure intent |
| --- | --- | --- |
| A13 | A local-only Skill declares external API/version lookup not applicable and validates without Context7, an MCP connection or network access. | A local fixture without network configuration passes; falsely declaring local-only while declaring a network/API dependency fails. |
| A14 | A version-sensitive Skill declares Context7-first lookup where available, official HTTPS fallback where unavailable, and version/source/retrieval-date records plus missing/stale-information behavior. | Missing version/source/date, HTTP fallback, arbitrary nonofficial fallback or absent failure policy fails. Historical records are syntax/provenance inputs, not proof of current latest versions. No lookup runs during static validation. |
| A15 | Secret-using capabilities name the runtime credential owner and safe reference mechanism, redaction policy and denied output locations. | Synthetic literal credential fields/known secret markers, a missing owner or raw secret-output policy fail. The tool reports location and rule only; no real credential fixture is permitted. It makes no universal secret-detection claim. |
| A16 | Destructive operations declare affected scope, required confirmation/authorization source and recovery or irreversibility disclosure. | Missing scope, a bypass flag or confirmation derived solely from untrusted input fails. Existing session/user authorization is valid where the owning policy accepts it; do not add a redundant confirmation for every operation. |
| A17 | Database-write capabilities declare backup/recovery prerequisites, transaction/failure handling and where the owning workflow records real backup/restore results. | Missing recovery contract or a fabricated 'already verified' declaration fails. No database capability requires no database/backup system. Static validation never counts as a restore drill. |
| A18 | Skills that consume untrusted content declare its data-only role and prohibit expansion of targets, commands, tool permissions or authority from that content. | A fixture with a machine-declared override of controller authority is invalid; embedded instructions in text are inert and never executed. Arbitrary prose is not claimed to be semantically injection-proof. |
| A19 | Filesystem capabilities declare contained roots, read/write/delete scope and traversal/symlink handling by an explicit owner. The validator itself enforces its local inspection boundary. | Escaping target/reference/fixture paths, a symlink to outside the package or a missing containment policy fails. Verify that a sentinel outside the root is neither read into output nor modified. |
| A20 | Subprocess capabilities declare argv, shell=false, cwd, finite timeout, bounded output and cancellation/process-tree owner. | Shell evaluation, absent timeout or absent cancellation owner fails. Do not create another Runner, job envelope, process tree controller or timeout engine in Package A. |
| A21 | Network capabilities declare allowed schemes/targets and an owner for redirects, DNS resolution, private/loopback/metadata blocking, controlled internal exceptions and timeout. | Arbitrary URL execution, HTTP downgrade or missing redirect/address policy fails declaration validation. Package A does not perform DNS, request a URL or install network tools. |

Capabilities may compose. Test a package that needs several capabilities and
reject a missing applicable control even when another capability is compliant.
Conversely, do not require network/database/subprocess/secret infrastructure
from a package that truthfully declares none of them. Prompt-injection and safe
parsing of inspected content remain baseline rules for the validator itself.

## FR-4: Migration compatibility and Package A terminal acceptance

| Intent | Required behavior and independent oracle | Negative/boundary case and failure intent |
| --- | --- | --- |
| A22 | Explicit inventory mode reports a pre-standard fixture as legacy; strict mode rejects it. A migrated fixture validates while retaining its owner-specific authority and lifecycle fields. | Absent quality sidecar must not be silently 'pass'. The migration fixture oracle compares explicit before/after owner and authorizes fields and fails on drift. This is a fixture/composition check, not a claim that the static validator can infer arbitrary Skill semantics. The validator never rewrites the inspected package. |
| A23 | The actual standard policy and both schemas validate with a small Package A reference package. That reference package is under the fixture tree and exercises the published CLI, not a test-local lookalike. | Inconsistent policy/schema versions, unused policy, schema-invalid result, dangling standard link and invalid reference package block terminal acceptance. The reference package is not an installed Skill or a new workflow entry. |
| A24 | One repository-owned pytest terminal selection executes all Package A unit, boundary, negative and CLI integration cases, with independent expected results and explicit case/assertion mappings. | Missing, skipped, deselected, xfailed, zero-case or harness-error required cases cannot pass; a negative fixture rejected as expected is a passing test, not an overall failed suite. |
| A25 | A Package B handoff table states the accepted quality contract/CLI, legacy behavior and expected migration touchpoints for the five Skills. It preserves the existing authority and the optional status of Bootstrap Review. | No Package A completion gate may require the five real Skills to pass the new standard or enable an internal reviewer. Excluded BMAD/GDS/Chapter 2-7 Skills remain excluded. |

'Clean package validation of the standard' means validation of the actual
published policy/schemas and the reference package against them, plus external
review of the normative standard. A Markdown standard is not itself an installed
Skill. Do not invent a governance Skill solely to validate that document.

The terminal command, after Q2 authors the declared tests, is:

```text
python -B -m pytest -q scripts/sc/tests/test_skill_quality_core.py scripts/sc/tests/test_skill_quality_examples.py scripts/sc/tests/test_skill_quality_capabilities.py scripts/sc/tests/test_skill_quality_migration.py
```

The terminal integration test calls the published CLI with a literal argv list,
`shell=False`, repository cwd and a finite timeout. It parses the fresh JSON,
checks the declared result schema and proves the reference package passes while
a mutated package is rejected. Merely observing exit 0, stdout containing an ID,
a file existing or a plan status string is insufficient.

## Implementation binding guidance

<!-- selector-repair-binding-start -->
### Source and execution baseline

Status: `requirements-input`; this file is not a published VDD plan.
Plan target: `execution-plans/2026-08-06-skill-authoring-standard`.
Source: `docs/workflows/skill-control-plane-evolution-requirements.md`, Package A.
Baseline: `f7ac19dbc1dde82e73f91854b5dc0c157c78703a` (main, 2026-10-18).

This scoped repair is the current Package A input. It retains the original
SAS-001 through SAS-012 outcomes and resolves their stale execution assumptions.
The legacy JSON, Bootstrap history and plan-local predicates are historical
inputs only. Their statuses do not authorize the current implementation.
See `LOCAL-HANDOFF.md` for compilation and the current Quick Dev entry.

The following NFR sections and test-authoring rules constrain VDD/Quick Dev
planning and execution through their existing owners. They are not new Package A
runtime features and must not become independent production-write slices.
Keep them in the generated write/forbidden/snapshot, failure-intent, validation
and terminal contracts. They remain binding even though V1 extracts only the
product source outside this authoring-context block. Do not reimplement the
completed 8-05/8-24 controllers or fabricate a production owner for a guard.

## NFR-1: Scope and authority limits

Package A implements only the standard, validator, reference fixtures and
migration guidance described above. It consumes the completed 8-05 toolchain
and 8-24 platform as its current baseline, without reopening either requirement
set. No code or test changes are authorized in:

- `.agents/skills/**`, `scripts/quick_dev/**`, `scripts/vdd/**`, or shared
  toolchain runtime/evidence writers; Package B owns later Skill migration.
- `PhaseA.Platform/**`, `PhaseA.Platform.Tests/**`, `runtime/**`, live metadata,
  hosted workspaces, Phase authentication/authorization and the Runner.
- `scripts/sc/_llm_backend.py`, model-routing policy or Codex shared entrypoints.
- Knowledge publication, Skill-input authority/generation stores, 7-31,
  TC-D2--TC-D6, BMAD/VDD knowledge-query changes, S1/S2/S3, or app-server/SDK.
- Historical Bootstrap, TDD, acceptance, freeze or implementation reports.

Do not add OIDC, a total-entry Skill, physical user deletion, user-installed MCP,
platform telemetry, a new error ledger, a second validation evidence system,
Godot runtime analysis, package installation or a mandatory internal review.
This standard cannot raise the tools/network ceiling of the user sandbox.

The standard ADR is proposed during drafting and accepted through the normal
maintainer decision before it is cited as new implementation authority. Do not
mark a draft ADR Accepted merely to satisfy a test. Existing ADR-0041 and
ADR-0058 (toolchain replay) own the preserved execution/evidence boundaries;
ADR-0061 owns the unchanged Phase isolation/recovery boundary.

## NFR-2: Current VDD and Quick Dev handoff

This repair uses VDD `self-hosted` because it introduces a controlling validator;
that choice adds only the relevant contract/migration fixtures. Development
governance is off. Do not add current frozen knowledge/Skill-input attestations,
source-freeze, reviewer signatures, internal Bootstrap, an authorization receipt
or a new 95 report. Preserve historical material without treating it as current.
External review remains useful, but is not fabricated as an internal receipt.

Only `scripts/vdd/compile_plan.py` can publish the current semantic plan and
`plan-ready`. Compiler output must cover every behavior above with its own
Acceptance, oracle, assertions, source references and failure intent. Structural
and scope constraints have explicit contract/terminal checks; absence of human
approval is not a product RED. All runtime-bearing obligations use the current
CER behavior-routing intent. Quick Dev, not VDD, assigns present/missing/
unverifiable after controlled case execution. Present behavior remains in
regression/terminal coverage and must not be reimplemented to manufacture RED.

Each executable failure intent names a planned pytest selector, real production
entry, expected observable AssertionError and bounded validation command. Do not
pre-create RED receipts, run IDs or process outcomes. A missing module, invalid
import, environment failure or absent planned test file is never causal RED.
Q2 authors only declared tests/helpers/fixtures and binds the real production
entry; if it cannot construct a valid oracle, repair the contract instead of
using a mock product or writing production before the allowed stage.

Tests, helpers, fixture bytes, selector, plan and Acceptance freeze before formal
RED. The implementation worker changes only the declared production owners.
Production owners must not also be immutable execution-snapshot inputs. Shared
production dependencies belong to current candidate/regression identity; later
changes invalidate affected earlier proof. Q6 has a nonempty applicable
regression list, and Q8 requires one current whole-plan terminal validation.
The implementation worker cannot review/accept its own output or commit/merge
on behalf of the maintainer.

All test helpers operate in disposable fixture roots. Intentional corruptions
and synthetic credentials are test data only. Tests invoke the real validator
entry/CLI and compare structured status, rule IDs, path, code and relevant
boundary effects. Tests must fail if the validator is replaced by an
unconditional pass implementation. No global scan of `.agents/skills` is a
Package A acceptance target. No Phase/Godot/Windows isolation suite is required
for this Python/static-standard change.

Q7/Q8 exact runtime
case coverage and Acceptance remain owned by the existing workflows.

This section is V3 authoring metadata, not additional product scope. Grouping
labels A1--A4 are suggestions, not published slice IDs or evidence identities.
The compiler may split atomic behavior lanes when necessary, but may not merge
independent oracles or omit any A01--A25 intent. Retain both NFR constraints
in the applicable generated boundaries and checks; their existing workflow
consumers are not new Package A implementation obligations.

| Group | Depends on | Intent coverage | Q2 test owner | Production owner |
| --- | --- | --- | --- | --- |
| A1 foundation | none | A01--A06 | scripts/sc/tests/test_skill_quality_core.py | standard, ADR/index, policy, schemas, validate_skill_quality.py |
| A2 declarations | A1 | A07--A12 | scripts/sc/tests/test_skill_quality_examples.py | validate_skill_quality.py, skill_quality_examples.py, policy/schema and standard refinements |
| A3 capability checks | A1, A2 | A13--A21 | scripts/sc/tests/test_skill_quality_capabilities.py | validate_skill_quality.py, policy/schema and standard refinements |
| A4 compatibility/terminal | A1, A2, A3 | A22--A25 | scripts/sc/tests/test_skill_quality_migration.py | validate_skill_quality.py, policy/schema and standard handoff guidance |

The exact production allowlist is the deliverable list under FR-1 plus
`scripts/sc/skill_quality_examples.py`. The Q2 allowlist is the four test modules
above, `scripts/sc/tests/skill_quality_support.py`, and
`scripts/sc/tests/fixtures/skill-quality/**` only. Q2 may author positive,
boundary, negative, legacy and migrated fixtures; it cannot modify production
or this requirements input. Green/refactor cannot modify frozen tests/fixtures.
No broad `scripts/sc/**`, `docs/adr/**` or `.agents/skills/**` write set is allowed.

Use one primary pytest case per intent named `test_a01` through `test_a25` in
its group test owner; use explicit parameter IDs for boundary variants. Thus
A04's selector is `scripts/sc/tests/test_skill_quality_core.py::test_a04`.
Each case binds its exact compiler-assigned CER assertion IDs. Each parameter
instance must execute; a marker on a shared helper cannot cover unexecuted cases.
All cases call the real production `validate_package` or CLI. Documentary
constraints use explicit artifact/contract assertions and a non-RED failure
role when they do not represent executable product behavior.

Targeted commands are the terminal argv limited to that group's test file;
Q6 includes relevant predecessor test modules, not later not-yet-authored tests.
A4's Q6 and terminal include all four test modules. Use argv arrays and timeouts:
300 seconds per targeted command, 900 seconds for terminal. Timeout is a harness
failure and never an accepted RED or evidence of a security denial.

After a local failure, retain its evidence and repair only the affected group
and dependents. A change to shared policy/schema/validator semantics invalidates
all affected case proofs; stabilize targeted checks before one terminal replay.
Missing or changed required sources trigger contract repair, not an automatic
knowledge publication, Bootstrap loop, new lineage, or out-of-scope patch.
<!-- selector-repair-binding-end -->
