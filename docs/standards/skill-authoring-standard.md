# Repository Skill Authoring Standard

Status: Draft normative contract for the authorized Package A implementation.
Decision: ADR-0041; proposed ADR-0062 records final adoption.
Standard version: 1.0. Rules: A01 through A25.

## Responsibility and lifecycle

Define exactly one primary responsibility, substantive triggers and non-goals,
accepted inputs and produced outputs, dependencies, references, tests, evidence
and lifecycle boundaries. Headings alone are not substantive declarations.
Package A performs read-only static declaration and fixture checks. It grants
no authority and claims neither runtime security nor product acceptance.
VDD owns plan-ready, Quick Dev owns implementation-complete, and Acceptance
owns acceptance-passed. Bootstrap Review is optional and owns no lifecycle state.
Existing Phase/Runner entrypoints retain OS, network, confirmation and recovery
enforcement; prose and JSON flags are declarations only.

## Frontmatter, identity and size

Use safe plain YAML frontmatter with name and description only. Both are
nonempty; name equals the canonical lowercase hyphenated package directory
and quality sidecar identity. Duplicate keys, constructors, malformed YAML and
unsupported frontmatter extensions are rejected. SKILL.md has fewer than 500
logical lines, counting frontmatter, blanks and code blocks. Prefer a smaller
main file; this recommendation is not a second hard gate. LF/CRLF count equally
and a final newline does not add a line.

## Versioned quality namespace

Use skill-quality.v1.json beside SKILL.md. Keep scripts/skill-contract.json and
references/skill-input-contract.v1.json unchanged and separate. All semantic
fields belong in this quality sidecar or first-level references. Unknown owned
fields, unsupported versions, malformed types and unknown capability names fail.
Required substantive fields: responsibility, triggers, non_goals, inputs, outputs,
dependencies, references, tests, evidence and lifecycle. Empty dependency and
reference arrays explicitly mean no such dependency/reference, not missing fields.

The contract declares schema=skill-quality.v1, standard_version=1.0, name,
authorizes=[], explicit boolean capabilities, lookup, controls, entrypoints,
examples, outcomes, routing, error_ids and optional FAQ/invocation records.
Capability keys are routing, version_lookup, secrets, destructive, database_write,
untrusted_content, filesystem, subprocess and network; all nine are explicit.
Each enabled capability requires its matching control declaration. An absent
capability requires no extra runtime infrastructure. Compatible capabilities
compose: one valid control never masks another missing control.

Substantive strings may instead use {"ref":"references/file.md#section"}.
References resolve inside the selected package. Required content uses a direct
first-level existing local file and anchor. Optional remote documentation is
never fetched and cannot substitute for required local content. Reject absolute,
traversal and symlink escapes before reading forbidden content. Policy/schema
and dependency authority inputs remain repository-contained. A policy link to
this standard resolves against repository_root, not package_root.

## Examples and routing

Exactly three ordered primary examples have outcome IDs typical, boundary,
error, nonempty input/output, branch and expected_result fields. These fields
are checked mechanically; external review judges their semantic usefulness.
Outcomes/branches must exist and be distinct. Identical normalized input/output
pairs under different labels fail. Supplemental referenced examples do not
change the primary set. Example outcomes alone do not make a leaf an
orchestrator. A real leaf declares routing.kind=leaf and needs no diagram.
An orchestrator declares routing.kind=conditional, entry, branch IDs and a
linked ASCII diagram containing reachable edges [source] -> [target]; all
primary branches must be reachable from the declared entry. False leaf
classification or missing/unresolved diagram branches fails.

## Dependencies and entrypoints

Dependency records declare id, required boolean, compatible version, local
authority and when_missing behavior. Required missing records, unresolved
authority and version conflicts yield typed A09 blocking diagnostics. No
dependency is invoked or installed, and required host installation is not
needed for static inspection. Optional absence names a resolvable safe fallback
that grants no protected-work authority. Policy dependency/version authorities
remain explicit local records.
Each public entrypoint declares id, inputs, outputs, preflight, standalone,
dependencies and caller_setup. Undeclared setup, silent installation and silent
skipping of required dependencies fail. No global total-entry Skill is added.
Complex checks declare script/test references, argv array, shell=false, contained
cwd, finite positive timeout and typed result. These commands are never executed
by this validator. FAQ is optional; each provided entry is reached from a stable
error ID or branch and has an existing local target.

## Capability declarations and safe inspection

Local-only lookup declares not-applicable and works without Context7/MCP/network.
A declared network/API dependency contradicts local-only. Version-sensitive
lookup declares Context7-first when available, policy-owned official HTTPS
fallback origins otherwise, version/source/retrieval_date, and missing/stale
handling. These are provenance records, not a latest-version or live freshness
service. No lookup executes.
Secrets name runtime credential owner, safe reference, redaction and denied
output locations. Synthetic literal credential markers or raw-secret output
fail, without echoing values; this is not universal secret detection. Destructive
controls declare scope, trusted authorization source and recovery/irreversibility.
Existing session/user authorization may satisfy the owning policy; do not demand
redundant confirmation. Bypass flags and untrusted-only confirmation fail.
Database writes name system, backup/recovery prerequisites, transaction/failure
handling and real-result record authority; unsupported already-verified flags
fail. Static validation is not a restore drill.
Untrusted content is data-only and cannot expand targets, commands, tools or
authority. Embedded prose remains inert; machine controller overrides fail.
Filesystem controls declare roots, read/write/delete scope, traversal/symlink
policy and owner. Subprocess controls declare argv, shell=false, contained cwd,
finite timeout, bounded output and cancellation/process-tree owner. Existing
Runner/job infrastructure remains unchanged. Network controls declare HTTPS
schemes/targets and redirect, DNS, private/loopback/metadata, controlled internal
exception and timeout owners. Arbitrary targets and HTTP downgrades fail.
Package A performs no DNS, URL request, network-tool installation or command.

## Public API, CLI and diagnostics

validate_package(*, repository_root, package_root, policy_path, mode="strict")
accepts pathlib paths and returns the same JSON-compatible object as the CLI:

```text
python -B scripts/sc/validate_skill_quality.py --repository-root . --policy scripts/sc/config/skill-authoring-standard.v1.json --skill-root <package> --mode strict
```

Relative caller paths resolve from repository_root. Absolute paths require
containment. Caller argv uses shell=false and a finite timeout (300 seconds for
targeted validation, 600 seconds for the whole-plan terminal).
The result schema is skill-quality-result.v1 with package identity, mode, status,
exit_code, ordered bounded rule/path/code/message diagnostics and authorizes=[].
0/pass, 1/fail, 2/error and 3/legacy are local validator exit semantics only.
Malformed package declarations fail/1; invalid invocation/inspection or unavailable
policy/schema errors return error/2. An otherwise inspectable absent-sidecar
package is legacy/3 only in inventory; strict is fail/1. Present invalid sidecars
never become legacy or pass. All CLI paths, including unknown arguments, print
one fresh JSON object with no usage text, raw inspected content or traceback.
Repeated identical inputs/policy produce equivalent sorted results without
timestamps, absolute host paths or environment secrets.

## Migration and Package B handoff

The reference package is a disposable fixture, not an installed workflow Skill.
Migration fixture comparisons preserve existing owner/lifecycle/authorizes fields
and reject drift; the static validator does not infer arbitrary Skill semantics.
It never rewrites the inspected package. Real policy, both schemas, this standard
and the reference fixture share version 1.0 and A01--A25 rule vocabulary. Policy,
schema, limit or rule drift must fail independently fixed checks.

| Skill | Quality contract and CLI | Legacy behavior | Migration touchpoints | Preserved authority | Bootstrap Review |
| --- | --- | --- | --- | --- | --- |
| VDD | skill-quality.v1.json; validate_skill_quality.py | inventory legacy/3; strict fail/1 | examples, dependency declarations, package checks | sole plan-ready publisher | optional |
| Quick Dev | skill-quality.v1.json; validate_skill_quality.py | inventory legacy/3; strict fail/1 | examples, entrypoints, package checks | implementation only; no review authority | optional |
| Bootstrap Review | skill-quality.v1.json; validate_skill_quality.py | inventory legacy/3; strict fail/1 | optional review declarations and examples | supplemental review; no lifecycle authority | optional |
| Acceptance | skill-quality.v1.json; validate_skill_quality.py | inventory legacy/3; strict fail/1 | input/result declarations and package checks | sole acceptance-passed publisher | optional |
| Knowledge Base | skill-quality.v1.json; validate_skill_quality.py | inventory legacy/3; strict fail/1 | local source/reference examples and package checks | existing publication owner unchanged | optional |

Package B owns actual migration of these five Skills. Package A completion never
requires all five real Skills to pass or an internal reviewer to run. BMAD, GDS
and Chapter 2-7 Skills remain excluded. Do not add a new governance Skill or
knowledge-query workflow. No Phase, Godot, Windows isolation or live runtime
redesign belongs to this static standard.

## Normative intent matrix

| A01 | The standard defines one primary responsibility, triggers, non-goals, I/O, dependencies, references, tests, evidence and lifecycle boundaries. A governed fixture missing a required declared section is rejected by the validator. | Remove a required declaration or its referenced section; validation must identify the rule and relative location, not accept headings alone. |
| A02 | The versioned quality contract schema accepts a valid contract, rejects unsupported versions, malformed types, undeclared fields in the owned quality namespace and unresolved references, and records capabilities explicitly. | A typo in a capability or schema version must fail; it must not silently become an empty/disabled capability. |
| A03 | Validate frontmatter, nonempty name/description, canonical package name and its consistency with the declared Skill identity. | Missing/malformed frontmatter, duplicate keys, conflicting name and unsupported frontmatter extension are invalid. Parse safely; YAML/object constructors must never execute. |
| A04 | Enforce fewer than 500 logical lines in SKILL.md, counting frontmatter, blank lines and code blocks; recommend a smaller main file without a second hard gate. | 499 lines pass and 500/501 fail. LF and CRLF have the same count; a final newline does not add an extra logical line. This preserves old SAS-A05 and Package B's below-500 boundary. |
| A05 | Required content moved out of SKILL.md remains reachable through a direct first-level local reference to an existing file and section. | Missing file/anchor, traversal, absolute path or symlink escape is rejected before reading outside the package. Optional remote documentation is not fetched and cannot substitute for required local content. |
| A06 | The public CLI and Python entry return deterministic structured results, correct exit semantics and a bounded list of rule/path/message diagnostics. | Malformed JSON, unreadable/out-of-root target, duplicate keys and unsupported contract versions cannot return pass. Two runs over identical bytes and policy yield equivalent sorted output, without timestamps or environment secrets. |
| A07 | Exactly three primary ordered examples cover typical, boundary and error routes; each has nonempty Input and Output tied to distinct declared example outcome/branch IDs and expected results. Supplemental examples may live in references and do not alter the primary set. | Missing/empty pair, wrong order, duplicate branch, unknown branch or identical normalized Input/Output with different labels fails. |
| A08 | Routing/orchestration Skills have a linked ASCII decision diagram whose declared reachable branch IDs include the three primary example routes. Leaf Skills are explicitly not applicable. | Missing diagram, unresolved branch or false leaf classification with declared routing fails. Do not require a diagram for a real leaf Skill. |
| A09 | Each dependency declares identity, compatible version or repository-owned authority reference, required/optional kind, and deterministic missing/mismatch behavior. | Missing required dependency record, incompatible declared version or unresolved local authority yields a typed blocking diagnostic; no dependency is executed. An optional absence follows its declared fallback, which itself must be resolvable and cannot authorize protected work. |
| A10 | Every public entry declares its accepted input, output, preflight and standalone behavior, including legitimate child dependencies. | A declaration that needs an undeclared caller setup, silently installs a missing child or silently proceeds past a required dependency fails. No global total-entry Skill is introduced. |
| A11 | Complex deterministic checks declare a script entry, test coverage and structured invocation with argv array, bounded timeout, explicit cwd, shell=false and typed result. | String shell command, missing/zero/unbounded timeout, unsafe cwd, missing script/test or untyped result fails static validation. The validator does not execute the supplied command to check it. |
| A12 | FAQ is optional. Every supplied FAQ entry is reached from a declared stable error ID or decision branch, with a resolvable local target. | No FAQ passes. Orphan entry, dead target and unknown error/branch fail; adding an otherwise unused FAQ is not required. |
| A13 | A local-only Skill declares external API/version lookup not applicable and validates without Context7, an MCP connection or network access. | A local fixture without network configuration passes; falsely declaring local-only while declaring a network/API dependency fails. |
| A14 | A version-sensitive Skill declares Context7-first lookup where available, official HTTPS fallback where unavailable, and version/source/retrieval-date records plus missing/stale-information behavior. | Missing version/source/date, HTTP fallback, arbitrary nonofficial fallback or absent failure policy fails. Historical records are syntax/provenance inputs, not proof of current latest versions. No lookup runs during static validation. |
| A15 | Secret-using capabilities name the runtime credential owner and safe reference mechanism, redaction policy and denied output locations. | Synthetic literal credential fields/known secret markers, a missing owner or raw secret-output policy fail. The tool reports location and rule only; no real credential fixture is permitted. It makes no universal secret-detection claim. |
| A16 | Destructive operations declare affected scope, required confirmation/authorization source and recovery or irreversibility disclosure. | Missing scope, a bypass flag or confirmation derived solely from untrusted input fails. Existing session/user authorization is valid where the owning policy accepts it; do not add a redundant confirmation for every operation. |
| A17 | Database-write capabilities declare backup/recovery prerequisites, transaction/failure handling and where the owning workflow records real backup/restore results. | Missing recovery contract or an 'already verified' flag without the declared record/authority reference fails. No database capability requires no database/backup system. Static validation never counts as a restore drill. |
| A18 | Skills that consume untrusted content declare its data-only role and prohibit expansion of targets, commands, tool permissions or authority from that content. | A fixture with a machine-declared override of controller authority is invalid; embedded instructions in text are inert and never executed. Arbitrary prose is not claimed to be semantically injection-proof. |
| A19 | Filesystem capabilities declare contained roots, read/write/delete scope and traversal/symlink handling by an explicit owner. The validator itself enforces its local inspection boundary. | Escaping target/reference/fixture paths, a symlink to outside the package or a missing containment policy fails. Use a forbidden-read sentinel to prove rejection before content access, and assert its bytes and diagnostic output remain unchanged/sanitized. |
| A20 | Subprocess capabilities declare argv, shell=false, cwd, finite timeout, bounded output and cancellation/process-tree owner. | A shell=true/string-command declaration, absent timeout or absent cancellation owner fails. Do not create another Runner, job envelope, process tree controller or timeout engine in Package A. |
| A21 | Network capabilities declare allowed schemes/targets and an owner for redirects, DNS resolution, private/loopback/metadata blocking, controlled internal exceptions and timeout. | An unrestricted arbitrary-target declaration, HTTP downgrade or missing redirect/address policy fails declaration validation. Package A does not perform DNS, request a URL or install network tools. |
| A22 | Explicit inventory mode reports a pre-standard fixture as legacy; strict mode rejects it. A migrated fixture validates while retaining its owner-specific authority and lifecycle fields. | Absent quality sidecar must not be silently 'pass'. The migration fixture oracle compares explicit before/after owner and authorizes fields and fails on drift. This is a fixture/composition check, not a claim that the static validator can infer arbitrary Skill semantics. The validator never rewrites the inspected package. |
| A23 | The actual standard policy and both schemas validate with a small Package A reference package. That reference package is under the fixture tree and exercises the published CLI, not a test-local lookalike. | Inconsistent policy/schema versions, unused policy, schema-invalid result, dangling standard link and invalid reference package block terminal acceptance. The reference package is not an installed Skill or a new workflow entry. |
| A24 | The repository-owned terminal selection exercises the actual public validator process, with CLI/API parity on valid, noncompliant, invocation-error and legacy inputs; assert fresh JSON, the independent expected status and the matching exit code for each case. | Ignoring mode, printing non-JSON/extra output, mismatched API/CLI diagnostics, or returning exit 0 for fail/error/legacy fails the bound case. Required case execution/skip/error closure belongs to existing CER/Q7/Q8; do not implement another test-runner or evidence writer. |
| A25 | A Package B handoff table states the accepted quality contract/CLI, legacy behavior and expected migration touchpoints for the five Skills. It preserves the existing authority and the optional status of Bootstrap Review. | No Package A completion gate may require the five real Skills to pass the new standard or enable an internal reviewer. Excluded BMAD/GDS/Chapter 2-7 Skills remain excluded. |
| A1 foundation | none | A01--A06 | scripts/sc/tests/test_skill_quality_core.py | standard, ADR/index, policy, schemas, validate_skill_quality.py |
| A2 declarations | A1 | A07--A12 | scripts/sc/tests/test_skill_quality_examples.py | validate_skill_quality.py, skill_quality_examples.py, policy/schema and standard refinements |
| A3 capability checks | A1, A2 | A13--A21 | scripts/sc/tests/test_skill_quality_capabilities.py | validate_skill_quality.py, policy/schema and standard refinements |
| A4 compatibility/terminal | A1, A2, A3 | A22--A25 | scripts/sc/tests/test_skill_quality_migration.py | validate_skill_quality.py, policy/schema and standard handoff guidance |

## Version 1 field reference

This section defines data declarations, never execution permission. Unknown
owned semantic fields fail. Owner-specific protocols retain their own files.

| Record | Version 1 fields |
| --- | --- |
| Dependency | `id`, explicit boolean `required`, exact requested `version` or locally resolved authority version, local `authority`, `when_missing`, `when_mismatch`; optional `kind` and `fallback` |
| Missing/mismatch handling | Required absence is `block`; optional absence is `fallback`; mismatch is `block`. No installation or implicit host discovery occurs. |
| Optional fallback | `ref` names a contained existing local file/section; `authorizes` is exactly `[]`. A fallback cannot grant protected work. |
| Public entry | `id`, nonempty `inputs` and `outputs`, `preflight`, boolean `standalone`, `dependencies`, explicit `caller_setup`; `install_missing` and `skip_missing`, when present, must be false. |
| FAQ entry | `from` is a declared error ID or routing branch; `target` is a local path or `{ "ref": "references/help.md#section" }`. |
| Invocation | `script`, `tests`, `argv`, `shell: false`, `cwd`, finite positive `timeout` at most 300, and `result_type`. This is inspected and never executed. |

Package-owned dependency authority paths are local relative paths under the
package. Policy-owned authority paths are local relative paths under the
repository. URI-shaped values cannot substitute for either authority, even
when a host happens to permit a similarly named local file. An exact version
is compared with its supplied local authority; no live version lookup or
installation determines conformance.

| Enabled capability | Control declaration |
| --- | --- |
| `secrets` | `owner`, safe `reference`, `redaction`, nonempty `denied_outputs`, `output_policy: "redacted"` |
| `destructive` | `owner`, `scope`, trusted `authorization_source`, and `recovery` or `irreversibility`; a bypass cannot confer authority |
| `database_write` | `owner`, `system`, `backup`, `recovery`, `transaction`, `failure`, local `record_authority` |
| `untrusted_content` | `owner`, `role: "data-only"`, `prohibit_expansion` covering targets, commands, tools and authority |
| `filesystem` | `owner`, contained `roots`, `read`, `write`, `delete`, `traversal: "reject"`, `symlinks: "reject"` |
| `subprocess` | `owner`, `argv`, `shell: false`, contained `cwd`, positive finite `timeout`, positive bounded `output_limit`, `cancellation_owner` |
| `network` | `owner`, HTTPS `schemes` and bounded `targets`, `redirect_owner`, `dns_owner`, `private_addresses`, `loopback` and `metadata` set to `block`, explicit `internal_exceptions`, bounded `timeout` |

An empty internal-exception list permits none. A declared exception names its
controlled internal MCP kind, owner and authority; the actual server policy
still decides access. These records do not perform DNS resolution, start a
process, read credentials or execute a restore drill.

## Author guidance for triggers, evidence and supported syntax

Invocation and applicability triggers state the concrete caller request or input
condition that makes the Skill applicable, and the condition that routes away
from it. The caller owns real execution evidence; evidence declarations name
its producer, record location, consumer and lifecycle, without transferring that
producer authority to the static validator.

The local JSON implementation supports a deliberately bounded schema subset
and rejects unsupported keywords and external references. Existing optional
jsonschema wrappers are scoped to their review-summary/execution protocols;
they cannot validate this contract without changing those unrelated owners.
No new dependency is required. Inputs are bounded to 1 MiB, depth 40 and
20,000 JSON values before semantic traversal. Plain frontmatter scalar fields
are strings; quote numeric/boolean-looking descriptions. An anchored reference
provides only its selected section through the next same-or-higher heading,
so an empty section cannot borrow unrelated text.

Accepted inputs describe required inputs, their interpretation and failure
behavior. Produced outputs describe their format and meaning to consumers.
Lifecycle ownership remains with the producing workflow, including evidence
retention and invalidation. Arbitrary inspected prose is not injection-proof.
ADR-0061 retains unchanged Phase isolation and recovery authority; ADR-0058
retains toolchain replay authority. This standard does not replace either.
