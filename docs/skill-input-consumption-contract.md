# Skill Input Consumption Contract

Status: Implemented (repository scope; declared strict Skills are fail-closed)

This document is the repository-level contract for determining whether a Skill
has consumed the complete and stable input required for its next authoritative
stage. It is independent of FastCtx. FastCtx is one transport implementation;
the contract also applies when a controlled child process or another approved
file reader supplies the input.

## 1. Scope And Ownership

The contract owns input discovery, completeness, source stability, reference
closure, semantic sufficiency, and the `ready` gate. It does not own file-reader
token limits, shell routing, lifecycle publication, acceptance authority, or
cross-session recovery.

The responsibilities are separated as follows:

| Layer | Responsibility |
| --- | --- |
| File transport | FastCtx `read/grep/glob/run` or another approved reader; bounded output and exact continuation offsets |
| Shared adapter | Discover declared sources, hash before/after, resolve references, freeze source bytes, and produce a deterministic model-safe snapshot |
| Semantic consumer | A controlled child reads only the model-safe snapshot and emits bounded Skill context plus a semantic decision |
| Validator | Recompute hashes and enforce the fail-closed `ready` gate before the Skill's authoritative stage |
| Skill contract | Declare its mode, trigger, required inputs, reference boundary, and semantic acceptance rule |

The FastCtx output contract is owned by
`docs/fastctx-file-operation-output-contract.md`. This document must not be
treated as a FastCtx configuration file or as a recovery protocol.

## 2. Consumption Modes

Every Skill that consumes repository files declares one mode:

| Mode | Use | Gate |
| --- | --- | --- |
| `none` | Only the current user message is consumed | No receipt is required |
| `bounded` | One or a few explicitly bounded files | Each source must report `Complete`; a temporary receipt is optional |
| `strict` | A long file, structured directory, referenced file graph, or complete evidence set | A validated receipt with `ready=true` is mandatory |

For `bounded`, omitting a receipt is allowed only for read-only reasoning. If
the next stage writes, generates a durable artifact, or makes an acceptance
decision, the owning evidence must record each source's exact-byte SHA-256
before and after consumption. A `Partial` result, reference expansion, or hash
change promotes the invocation to `strict` or fails closed.

`ready=true` means only that the declared input has been consumed and accepted.
It does not authorize writing, implementation, acceptance, release, or archive.

## 3. Contract And Receipt

Each `strict` Skill supplies one machine-readable contract at the fixed path
`.agents/skills/<skill-id>/references/skill-input-contract.v1.json`. The shared
JSON Schemas are owned by
`scripts/sc/schemas/skill-input-contract.v1.schema.json`,
`scripts/sc/schemas/skill-input-consumption.v1.schema.json`,
`scripts/sc/schemas/skill-input-source-manifest.v1.schema.json`,
`scripts/sc/schemas/skill-input-child-output.v1.schema.json`,
`scripts/sc/schemas/skill-input-context.v1.schema.json`, and
`scripts/sc/schemas/skill-semantic-decision.v1.schema.json`. The typed child
request is owned by `scripts/sc/schemas/skill-input-child-request.v1.schema.json`.
The child response shape is owned by
`scripts/sc/schemas/skill-input-child-output.v1.schema.json`.
The shared entry points are `scripts/python/prepare_skill_input_consumption.py`,
`scripts/python/launch_skill_input_consumer.py`, and
`scripts/python/validate_skill_input_consumption.py`. Existing workflow
entrypoints may call `scripts/python/skill_input_gate.py` to require the exact
consumer/operation receipt before their first authoritative action.

`launch_skill_input_consumer.py --run-semantic-child` requires explicit
`--backend` and `--model` values from the owning route. It uses the shared
`scripts/sc/_llm_backend.py` stdin-first backend, creates an isolated temporary
child root containing only the model-safe snapshot, and publishes only typed
context/decision sidecars. It never selects a provider or falls back to raw
child output.

Example contract:

```json
{
  "schema_version": "skill-input-contract.v1",
  "consumer": "vdd-execution-plan",
  "mode": "strict",
  "trigger": "after-route-before-source-freeze",
  "source_roles": {
    "explicit_task_sources": {
      "selector": "caller_explicit_paths",
      "required": true,
      "root": "repository",
      "allowed_kinds": ["file", "directory"],
      "reference_kinds": ["markdown-link", "json-path-field"]
    },
    "target_plan": {
      "selector": "caller_target_plan",
      "required": true,
      "root": "execution-plans",
      "allowed_kinds": ["directory"],
      "reference_kinds": ["json-path-field"]
    },
    "explicit_repair_sources": {
      "selector": "caller_explicit_repair_paths",
      "required": true,
      "root": "repository",
      "allowed_kinds": ["file", "directory"],
      "reference_kinds": ["markdown-link", "json-path-field"]
    }
  },
  "operations": {
    "create": {"required_inputs": ["explicit_task_sources"]},
    "repair": {"required_inputs": ["target_plan", "explicit_repair_sources"]}
  },
  "reference_policy": "declared-in-root-and-contained",
  "max_reference_depth": 32,
  "max_sources": 500,
  "max_context_bytes": 12000,
  "budget_basis": {
    "path": "tests/fixtures/skill-input/vdd-create-baseline.json",
    "sha256": "sha256:..."
  },
  "sensitivity_policy": "deny-credential-values",
  "redaction_profile": "credential-values-v1",
  "forbidden_sources": ["logs-as-recovery-source"],
  "semantic_acceptance": "all-required-inputs-are-sufficient"
}
```

Every `required_inputs` value must resolve to exactly one declared
`source_roles` entry. A role's `required` value is scoped to the operation that
lists that role; an unlisted role is not required for the current operation.
Selectors accept only caller-supplied typed paths; they do not enumerate sibling
plans, infer a target, or search logs. Unknown selectors, operations, schema
versions, or fields fail closed. Current schemas use `additionalProperties: false`.
Every `strict` contract must also require `budget_basis`, `sensitivity_policy`,
and `redaction_profile`; omission is a schema failure, not an implicit default.

The shared adapter emits a temporary or authorized plan-local
`skill-input-consumption.v1` receipt:

```json
{
  "schema_version": "skill-input-consumption.v1",
  "consumer": "skill-id",
  "operation": "create|repair|review|execute|acceptance",
  "request_hash": "sha256:...",
  "request_binding": {
    "request": {},
    "consumer": "skill-id",
    "operation": "create|repair|review|execute|acceptance",
    "target": "execution-plans/example",
    "route_identity": "strict_tdd_plan",
    "source_roles": {"requirements": ["requirements.md"]}
  },
  "target": "execution-plans/example",
  "route_identity": "strict_tdd_plan",
  "repository_identity": {
    "head": "<git-object-id>",
    "index_hash": "sha256:...",
    "scoped_worktree_hash": "sha256:..."
  },
  "adapter_version": "skill-input-adapter.v1",
  "created_at": "RFC3339 timestamp",
  "contract_hash": "sha256:...",
  "source_manifest": {
    "path": ".../source-manifest.v1.json",
    "sha256": "sha256:..."
  },
  "child_request": {
    "path": ".../skill-input-child-request.v1.json",
    "sha256": "sha256:..."
  },
  "sources": [
    {
      "path": "...",
      "required": true,
      "sha256_before": "sha256:...",
      "sha256_after": "sha256:...",
      "size_bytes": 0,
      "line_count": 0,
      "sensitivity": "normal|restricted|credential-bearing",
      "semantic_snapshot_sha256": "sha256:...",
      "redaction_status": "not-required|complete|failed",
      "ranges_consumed": [
        {"unit": "line", "start": 1, "end": 1}
      ],
      "transport_status": "complete|partial|failed|changed",
      "semantic_status": "accepted|insufficient|not-evaluated"
    }
  ],
  "missing_sources": [],
  "changed_sources": [],
  "semantic_decision": {
    "path": ".../semantic-decision.v1.json",
    "sha256": "sha256:...",
    "status": "accepted|insufficient"
  },
  "diagnostic_authorization": null,
  "context_artifact": {"path": "...", "sha256": "sha256:..."},
  "authorizes": [],
  "binding_hash": "sha256:...",
  "ready": false
}
```

`binding_hash` is the canonical hash of the receipt with `binding_hash` itself
omitted. It covers the contract, operation, request, route, target, repository
identity, adapter version, `source_manifest.sha256`, every source hash and
coverage range, sensitivity classification, semantic-snapshot/redaction hash,
child request, semantic decision, and context artifact. The adapter emits a candidate with
`ready=false`; the validator recomputes all fields and atomically publishes the
final `ready` value and matching `binding_hash`.

`contract_hash`, source hashes, and artifact hashes are SHA-256 over exact file
bytes. `request_hash` and `binding_hash` use the repository canonical JSON
encoding: UTF-8, recursively sorted object keys, and no insignificant
whitespace. Repository paths are normalized to repository-relative
forward-slash form after resolved-root and symlink containment checks. The
validator rejects absolute machine-specific paths and credential-bearing values
inside persistent request bindings. It also recomputes the Git HEAD, index, and
scoped worktree identity instead of trusting the receipt's stored identity.

`request_hash` is recomputed from the stored `request_binding`, which covers the
typed caller identity, consumer, operation, target, route, and explicit source
roles and paths; it excludes timestamps and temporary paths.
Artifact paths in a receipt are relative to the receipt root. `resume` is not a
new operation: it reuses the original operation and byte-identical binding. A
changed request, repository identity, contract, source, or artifact creates a
new binding.

The adapter reads the verified source bytes twice in the non-model parent,
binds their before/after hashes in `source-manifest.v1.json`, applies the
contract's deterministic sensitivity policy, and atomically emits only the
model-safe snapshot. Actual credential values remain only in the authoritative
live source and transient parent memory; they are never copied into protocol
artifacts or included in the child request, context artifact,
model-facing diagnostic output, published evidence, or committed file. An
explicitly authorized non-model platform diagnostic may retain access-controlled
operational evidence under the repository security boundary, but it still may
not pass actual credential values to a model or publish/commit them.

Text coverage is represented by ordered,
non-overlapping, inclusive line ranges and must cover line 1 through
`line_count`; an empty text file is complete with `line_count=0` and no ranges.
Binary sources are rejected unless the Skill contract declares an approved
binary parser and its exact byte coverage rule. Encoding failures are
`transport_status=failed`. Structured parsers additionally bind the exact source
bytes. Directory sources are complete only when their sorted contained-path
manifest has been fully processed. The raw snapshot is never returned to the
main session.

The launcher sends a typed `skill-input-child-request.v1` containing only the
model-safe snapshot root, source-manifest hash, consumer, operation, contract
hash, and an output directory. It binds the child executable/model/sandbox
identity and rejects any extra path or tool capability. The controlled semantic
child reads only that frozen snapshot and declared, hash-bound detached
fixtures. It writes the bounded `context_artifact` and semantic decision to the
separate output directory and cannot modify the snapshot or receipt. The context
artifact is what the parent Skill receives; the receipt alone is not a
substitute for task content. The artifact must not contain raw logs or unrelated
tool transcripts.

The child request has this minimum shape:

```json
{
  "schema_version": "skill-input-child-request.v1",
  "consumer": "skill-id",
  "operation": "create|repair|review|execute|acceptance",
  "contract_hash": "sha256:...",
  "source_manifest_hash": "sha256:...",
  "snapshot_root": "model-safe-binding-relative-path",
  "output_root": "temporary-binding-relative-path",
  "execution_identity": "sha256:...",
  "max_context_bytes": 12000,
  "allowed_capabilities": ["read-frozen-snapshot", "write-context-output"],
  "authorizes": []
}
```

The launcher rejects a request with an absolute path, a capability outside the
allowlist, or an execution identity that does not match the controlled process
receipt. Ready publication hash-binds that exact child request and verifies its
consumer, operation, contract, manifest, output root, context budget, and
execution identity against the semantic decision; detached sidecars cannot be
published without it.

The validator sets `ready=true` only when all required sources are discovered,
transport is `complete`, before/after hashes match, declared references are
closed, the semantic decision is valid and bound to the same context artifact,
the declared budget has a fixture basis, the sensitivity/redaction policy has
passed, and the context artifact hash matches the receipt. `partial`, `failed`,
`changed`, missing, ambiguous, escaping, unbounded, or log-only sources fail
closed.

The semantic decision is a non-authorizing `skill-semantic-decision.v1` result.
It must contain the producer role and execution identity, source-manifest hash,
context artifact hash, per-source semantic statuses, decision status, bounded
rationale (at most 2,000 UTF-8 bytes), `redaction_status`,
`redaction_profile_hash`, and `authorizes: []`. The validator projects those
per-source values into the receipt and rejects any disagreement. A
`credential-bearing` source must have `redaction_status=complete` and may
produce only a redacted derived value. If the task requires the credential value
itself, the gate returns `ready=false` and routes to an explicitly authorized
non-model platform diagnostic whose output is redacted before any model sees it.
The child may not read raw live sources, parent memory, logs, or write the
receipt.

The optional `diagnostic_authorization` is required whenever a contract allows
credential-bearing input to enter a non-model diagnostic. It must contain an
authority path, exact authority SHA-256, operation scope, repository/target
binding, issuer, and `expires_at`. The validator rejects missing, expired,
scope-mismatched, or stale authorization. A diagnostic emits a separate
redaction receipt before any derived result can enter a model context.

## 4. Trigger Protocol

Skills are Markdown instructions and have no implicit post-load execution hook.
The trigger is therefore an explicit call made by the owning workflow launcher
after the Skill has selected its route and before its first authoritative stage.

The common sequence is:

```text
load Skill authority
  -> select operation and route
  -> load the Skill input contract
  -> shared adapter discovers sources and freezes source plus model-safe snapshots
  -> semantic child reads the model-safe snapshot and emits bounded context plus a decision
  -> validator verifies skill-input-consumption.v1
  -> ready=true gate
  -> Skill enters its normal generation, modification, execution, or acceptance stage
```

When `ready=false`, the launcher may only perform bounded inspection, request a
material clarification, or route to repair. It must not continue by returning
the same incomplete content through another tool.

The adapter must use explicit absolute or repository-contained paths, preserve
UTF-8, reject path escape, and record hashes from the same byte snapshot that
was consumed. A log may be evidence for a current diagnostic when a Skill's
contract explicitly permits it, but a log is never a recovery source for missing
task context.

### 4.1 Mandatory Launcher Integration

The contract remains non-authorizing until all four initial consumers have both
the companion contract file and an explicit launcher gate:

| Consumer | Gate placement | First blocked action |
| --- | --- | --- |
| `vdd-execution-plan` | after `create/repair` route and authority reads | knowledge freeze or plan artifact generation |
| `quick-dev-tdd-adapter` | after route and minimum target discovery | action selection, `prepare`, or RED |
| `run-phase-bootstrap-review` | after closure selection | Artifact View freeze or reviewer launch |
| `run-refactor-implementation-acceptance` | after prerequisite resolution | `start-or-resume` |

Each Skill must name the shared adapter and validator commands in its `SKILL.md`
and fail closed when the receipt is missing, stale, false, or bound to another
request. A contract file or receipt without this Skill-level gate is not an
active integration. The gate must be covered by a producer/consumer composition
test, not only by a standalone validator fixture.

## 5. Required Skill Changes

Only Skills using `bounded` or `strict` input need changes. The shared adapter
and validator are implemented once; each Skill contributes a declaration and a
single gate call.

### 5.1 VDD Execution Plan

Add a `skill-input-contract.v1` declaration under the VDD Skill and invoke the
adapter after `create` or `repair` is confirmed, after mandatory Skill authority
reads, and before knowledge preflight/source freeze or plan artifact generation.

- `create` requires the explicit requirements file or structured requirements
  directory and all declared in-boundary references.
- `repair` requires the target plan's normative files plus the explicit finding
  or repair inputs; historical reports and logs cannot fill missing sources.
- `plan-ready` validation must require the current receipt and context artifact.
  The VDD knowledge-preflight result records `skill_input.binding_hash` and the
  validated context-artifact path for its owning launcher.

Standalone requirements Markdown remains direct implementation input and must
not activate this gate unless the user explicitly requests a complete VDD plan.

### 5.2 Quick Dev TDD Adapter

Declare `strict` with trigger `after-route-before-prepare`. After the parent
router returns `lane=strict_tdd_plan`, perform only the minimum target identity
and contract discovery needed to build the source list. Then invoke the
adapter before action/state selection, `prepare`, implementation identity
freezing, or observing RED. Discovery reads are input reads, not lifecycle
state decisions, and must be recorded in the receipt.

- The target must be one explicit `execution-plans/<target>` directory.
- Required sources include the schema-valid
  `implementation-contract.v1.json`, its declared plan inputs, and any
  explicitly frozen knowledge context.
- A missing, ambiguous, changed, or schema-invalid source routes to repair and
  cannot enter a slice.
- Persist the receipt binding and context-artifact hash in recovery state so a
  resumed slice cannot detach from the consumed input.

### 5.3 Bootstrap Review Skill

`run-phase-bootstrap-review` declares `strict` with trigger
`after-closure-before-prepare`. After the caller has selected the review
operation and minimal complete closure, invoke the adapter before `prepare`
freezes the Artifact View or any reviewer process can launch.

- Required sources include the declared review scope, direct consumers,
  validators, repository authority, standards, and current acceptance evidence.
- A directory scope still requires the Skill's existing
  `directory-is-minimal-complete-closure` attestation; the consumption receipt
  cannot manufacture that attestation.
- Bind the receipt and context-artifact hash into the review preparation input.
  Bootstrap's Artifact View, access proof, and launch authorization remain
  independent gates.
- A failed child or malformed semantic response is a transport attempt failure
  and may retry in the same run; it does not create a new semantic review round.

### 5.4 Refactor Implementation Acceptance Skill

`run-refactor-implementation-acceptance` declares `strict` with trigger
`after-prerequisites-before-start-or-resume`. Once the target plan, candidate or
dirty-worktree identity, implementation contract, manifests, action DAG,
command registry, and frozen knowledge context have been explicitly resolved,
invoke the adapter before `start-or-resume` publishes a persisted run.

- Required sources include the complete acceptance prerequisite bundle and all
  explicit producer/consumer paths used by the acceptance actions.
- Bind the receipt, contract hash, and context-artifact hash into the canonical
  run input. Any drift creates a new binding or a repair route; it never mutates
  an existing run.
- `ready=true` only permits Acceptance orchestration to continue. It cannot
  publish `acceptance-passed`, authorize commit, release, or archive.

### 5.5 Source Graph And Artifact Rules

Each contract declares a repository-contained root, allowed reference kinds,
`max_reference_depth` (default 32), and `max_sources` (default 500). The
adapter rejects cycles, symlink escapes, external references, duplicate
canonical paths within one explicit role, and limits exceeded. Converging
references are de-duplicated by canonical path. `max_sources` and `max_context_bytes`
must be finite positive integers and must cite an existing hash-bound
`budget_basis` fixture; an override without a passing fixture is invalid. A
reference is consumed only after its target is present in the same source
manifest.

For `json-path-field`, `$ref` and object keys whose final camelCase/snake_case
word is `path`, `paths`, `file`, `files`, `filepath`, `filepaths`, `filename`,
`filenames`, `directory`, or `directories` declare references. Matching is
case-insensitive, so camelCase and snake_case are equivalent without treating
words such as `profile` as `file`. Generic semantic fields such as `source`,
`target`, and `reference` do not declare paths by themselves.
For a path-like key, a bare value without a separator, leading dot, or filename
suffix is treated as a semantic name rather than a source reference; directory
references outside the current source tree therefore use `./name` or another
explicit relative path. Path-like references that are explicit but missing
still fail closed.
Glob and selector values containing `*`, `?`, or bracket expressions describe
scope rather than one concrete source and do not enter the source graph.
Reference traversal remains recursive only inside the caller's explicit source
root. A concrete target outside that root is added to the manifest as a
hash-bound leaf, but its own links and path fields are not reinterpreted. This
prevents an explicit plan input from recursively promoting historical snapshots,
backups, or unrelated evidence trees into new recovery authority.

The default context artifact is an atomic UTF-8
`skill-input-context.v1.json` file under the temporary binding directory. Its
default limit is 12,000 UTF-8 bytes; a Skill contract may declare a different
finite `max_context_bytes`. The artifact records its source-hash set,
truncation state, omitted items, and semantic sections. `truncated=true` always
produces `semantic_status=insufficient` and `ready=false`.

After atomic ready publication, copied model-safe source bytes are deleted while
the hash-bound source manifest is retained. A resumable Skill may persist the
manifest, child request, context, decision, and receipt only in its authorized plan state
directory with the receipt binding; raw or copied source bytes are not persisted
by this protocol and no protocol artifact may be placed under `logs/`. A persistent receipt is valid
only while every referenced manifest, child request, context, and decision sidecar exists,
remains byte-identical, and passes the same validator. Missing, stale, or
unreadable sidecars produce `ready=false`. Atomic publication requires staging
complete bytes, fsync where supported, and replacing only an absent or
byte-identical destination. The sole state transition exception is candidate
`ready=false` to validated `ready=true`, which uses an exact expected-byte
compare-and-swap.
Before that compare-and-swap, the complete proposed ready receipt is written to
a unique sibling staging artifact and passes the same `require-ready`
validation. A failed budget, source, repository-identity, sidecar, or semantic
check leaves the candidate receipt byte-identical and cannot publish an invalid
`ready=true` state. Snapshot payload bytes use the same absent-or-byte-identical
write rule, so another binding cannot overwrite an existing candidate snapshot.

The semantic child's isolated temporary execution root is removed by the
launcher on normal completion, cancellation, timeout, or child failure. A
candidate model-safe snapshot remains available only for same-binding transport
retry; ready publication removes its copied source payload. Stale candidate
bindings are non-authorizing and may be removed by bounded maintenance using
their receipt roots; cleanup never returns snapshot bytes to the main session.

The same `binding_hash` may resume idempotently after a transport interruption.
A changed binding requires a new receipt. The adapter must never retry the same
failed parameters after a semantic failure, and must never fall back to raw
source output.

### 5.6 Other Skills

Classify each Skill once:

- `none`: no change;
- `bounded`: add a `Complete` check at the existing read boundary;
- `strict`: add a contract file, adapter call, context-artifact handoff, and
  validator gate.

Do not add the protocol to every Skill by default. A Skill that does not consume
external files must remain `none`.

## 6. Implementation Order

1. Create the shared contract, consumption, context, semantic-decision, and
   child-request schemas, redaction rules, and validator.
2. The shared adapter, model-safe snapshot producer, typed child boundary, and
   receipt validator are implemented under `scripts/python/`. The semantic child
   remains the only context/decision producer; `--publish-ready` requires the
   exact child request and is the explicit atomic receipt publication step.
3. VDD, Quick Dev TDD, Bootstrap Review, and Refactor Acceptance each declare a
   contract and gate at its first authoritative action. Their existing lifecycle
   remains the owner of route, write, review, and acceptance decisions.
4. Keep extending the fixture matrix with source-graph, semantic-decision,
   idempotent-resume, artifact cleanup, sensitivity, and malformed-child cases
   before migrating additional Skills.
5. Record validation evidence under `logs/`, but keep receipts and their
   protocol sidecars in the authorized plan state or temporary binding root.
   Evidence may reference their hashes; logs never become recovery input.

## 7. Validation Matrix

After the shared scripts exist, run:

```powershell
py -3 scripts/python/validate_skill_input_consumption.py <receipt.json> --contract <contract.json> --require-ready
py -3 scripts/python/launch_skill_input_consumer.py --request <child-request.json> --binding-root <binding-root> --run-semantic-child --backend codex-cli --model <explicit-model>
py -3 -m unittest discover -s scripts/python/tests -p "test_skill_input_consumption*.py"
py -3 .agents/skills/vdd-execution-plan/scripts/validate_skill_contract.py --skill-root .agents/skills/vdd-execution-plan
py -3 -m unittest discover -s .agents/skills/vdd-execution-plan/scripts/tests -p "test*.py"
py -3 -m unittest discover -s .agents/skills/quick-dev-tdd-adapter/tools/tests -p "test*.py"
py -3 -m unittest discover -s .agents/skills/run-phase-bootstrap-review/tests -p "test*.py"
py -3 -m unittest discover -s .agents/skills/run-refactor-implementation-acceptance/tests -p "test*.py"
```

Each Skill integration also runs its existing contract/unit suite. The shared
fixture matrix must include:

| Fixture | Expected result |
| --- | --- |
| Complete stable single file | `ready=true` |
| Empty UTF-8 text file | `ready=true` with zero ranges |
| Undeclared binary or encoding failure | `ready=false` |
| Multi-page file with all exact offsets | `ready=true` |
| `Partial`, missing source, or source hash drift | `ready=false` |
| Unknown operation, selector, schema version, or field | schema failure |
| Reference cycle, depth/source limit, symlink or root escape | `ready=false` |
| Semantic decision bound to another context artifact | `ready=false` |
| Truncated or oversized context artifact | `ready=false` |
| Credential-bearing source without complete redaction | `ready=false` |
| Same binding after transport interruption | idempotent resume |
| Same receipt with another target/request/route | binding failure |
| Missing, stale, or unreadable persistent sidecar | `ready=false` |
| Malformed child JSON, timeout, or unexpected child exit | transport failure; no raw fallback |
| Raw log used as task recovery input | `ready=false` |

The composition suites must prove that each Skill's first authoritative command
rejects a missing, stale, or false receipt, not merely that the shared validator
rejects a standalone fixture.

## 8. Acceptance Criteria

- A strict Skill cannot enter its authoritative stage with `ready=false`.
- Complete input is transported once into a bounded context artifact; raw
  logs, rollout files, and unrelated tool output are not returned to the main
  context.
- Hash drift, missing references, partial reads, path escape, and semantic
  insufficiency all fail closed.
- VDD `create`/`repair`, Quick Dev TDD, Bootstrap Review, and Refactor
  Implementation Acceptance have passing composition tests.
- Fixtures prove missing references, path escape, cycles, source drift,
  semantic-decision/context mismatch, duplicate retry, and oversized context
  artifacts all fail closed.
- `none` Skills remain unaffected and no Skill receives an implicit recovery
  or acceptance authority from this protocol.
