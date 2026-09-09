# Skill-input v2 direct adapter

Authority: Accepted ADR-0060. The current entry is
`scripts/python/skill_input_v2.py`; it does not invoke VDD, Quick Dev,
Bootstrap, Acceptance, a model, or Knowledge publication. It may deliver bytes
to an actual transport supplied by a Python consumer. CLI `consume` delivers
redacted UTF-8 pages to stdout. Delivery/coverage is not a claim about model
comprehension or semantic acceptance.

## Consumers and compatibility

| Consumer | Contract operations |
| --- | --- |
| vdd-execution-plan | create, repair |
| quick-dev-tdd-adapter | execute |
| run-phase-bootstrap-review | review |
| run-refactor-implementation-acceptance | acceptance |

Bind the corresponding existing consumer contract; the adapter verifies its
consumer and operation. Pass the canonical `current.v1.json` to
`skill_input_gate.require_ready_skill_input` or
`validate_skill_input_consumption.validate_receipt`. The shared gate resolves
and revalidates the immutable generation against current sources and bindings.
V1 receipt paths still use the existing explicit compatibility behavior. No
existing V1 receipt is copied, renamed, or promoted into V2 current authority.
Existing workflow orchestrators are not invoked by this direct route.

## Explicit request

A `skill-input-request.v2` object has these required fields:

- `plan_id`, `consumer`, `operation`, `policy_revision`: nonempty safe identifiers.
- `storage`: repository-relative dedicated output directory for one consumer
  and operation, for example `execution-plans/example/skill-input-v2/quick-dev`.
- `sources`: explicit file rows, each with `role`, `path`, `module`,
  `resource_set`, `authority`, `sha256` (`sha256:` plus 64 lowercase hex digits).
- `bindings`: exactly `contract`, `registry`, `authority`, `knowledge_freeze`,
  each a repository-relative `path` and hash of the file's exact bytes.

Optional integer budgets: `page_bytes` (default 32768, at least 4),
`max_snapshot_bytes` (default 8388608), `max_retries` (default 2, maximum 10).
`changed_paths` is the explicit candidate changed set used for Knowledge
self-change review routing; include additions, edits and deletions, not only
selected input files. Do not pass a caller-authored `knowledge_self_change` flag.

Every source has one role: normative_source, authority_source,
implementation_input, lifecycle_projection, derived_context,
execution_evidence, report, or ephemeral_attempt. Only the first three enter
the read set. There is no discovery from filename exclusion lists. Duplicate,
ambiguous, missing and escaping paths fail. Output storage cannot be selected
as input. Selected source hashes are verified from current bytes. Consumer,
policy, path, role, module, resource set and authority determine selection;
content has a separate identity.

Knowledge freeze supports two explicit modes:

1. Existing `jimuyun.vdd-knowledge-freeze.v1` or
   `jimuyun.knowledge-consumer-freeze.v1`: context hash, current publication,
   LKG, source selection and refreshed read set use the existing Knowledge
   validator. Unsupported/missing/invalid state blocks. Refresh is in memory
   and is bound into the new input receipt; no Knowledge generation is written.
2. `skill-input-direct-source-freeze.v2`: exactly `schema_version`,
   `sourceSelectionHash`, `authorizes: []`. This is an explicit direct-source
   mode for work without a Knowledge publication dependency. Derive the hash
   with `skill_input_selection.selection_identity`; it is not a fake Locator
   freeze and cannot claim a Knowledge gate passed.

A same-selection, non-authority source-byte change may use `prepare
--allow-refresh`. Selection/authority drift requires repairing the explicit
request/freeze and choosing its newly authorized scope; it cannot silently
replace an existing current route. Do not use a fresh storage directory merely
to conceal a blocked scope change.

## Run and resume

Run from the repository root (PowerShell examples):

```powershell
py -3 scripts/python/skill_input_v2.py prepare --request request.v2.json
py -3 scripts/python/skill_input_v2.py consume --plan-id example --attempt-id <returned-id> --max-pages 1
py -3 scripts/python/skill_input_v2.py heartbeat --plan-id example --attempt-id <returned-id>
py -3 scripts/python/skill_input_v2.py finish --plan-id example --attempt-id <returned-id>
py -3 scripts/python/skill_input_v2.py validate --pointer <storage>/current.v1.json --consumer quick-dev-tdd-adapter --operation execute --contract .agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json
```

Repeat consume until `status=complete`. Its persisted continuation binds plan,
selection, content, pages and offset. `--continuation token.json` optionally
requires the previously returned exact token and rejects stale retries. An
actual transport callback returns normally only after accepting a page. A
TimeoutError/OSError does not advance coverage; bounded retry state persists.
After lease expiration or terminal failure, prepare a new attempt rather than
editing the old attempt metadata. Attempts are under
`.skill-input-work/<plan-id>/<attempt-id>/` and have a 300-second renewable lease.

Finish recomputes exact byte/line/hash coverage from current redacted source
bytes. It writes a complete immutable generation under
`<storage>/skill-input-generations/<content-hash>/`, validates it, then
atomically replaces the single non-authorizing current pointer. Identical
replay reuses the generation. Partial transport, stale bindings, incomplete
staging and failed validation cannot replace current. Concurrent publisher
coordination is outside this single-maintainer protocol; use one writer per
storage root.

## References and retention

Before retiring current or handing a generation to lifecycle/authorization/
terminal/acceptance evidence, register the native artifact reference:

```powershell
py -3 scripts/python/skill_input_v2.py reference --storage <storage> --reference-id handoff-1 --kind terminal --artifact <repo-relative-artifact.json> --generation-id <id>
py -3 scripts/python/skill_input_v2.py gc --storage <storage> --plan-id example --dry-run
```

The native artifact must actually contain the declared generation_id or
generation_ids. Registration is immutable and binds its bytes. Stale references
block GC; they are not silently dropped. Current, explicit references,
unexpired leases, retention-window objects and incomplete staging are protected.
Never infer external references by searching unrelated log trees. Consumers
must register external ownership before the generation ceases to be current.

GC defaults to dry-run. Apply requires a separately supplied JSON approval with
exact fields: schema_version=`skill-input-gc-approval.v1`,
approved_by=`maintainer`, plan_hash from the current dry-run, and the same
predecessor_commit. The repository must have an actual Git HEAD. This rule
applies to untracked as well as committed candidates. A changed plan, reference,
object hash or commit requires fresh approval. Implementation authorization is
not cleanup authorization.

```powershell
py -3 scripts/python/skill_input_v2.py gc --storage <storage> --plan-id example --apply --approval <approval.json>
```

Apply records the full candidate/protection list, reasons, bytes, predecessor,
approval hash and actual removals in non-authorizing started/result sidecars.
An interrupted removal is not a successful cleanup. This implementation's tests
remove only detached temporary fixtures, never repository historical evidence.

## Direct verification

```powershell
py -3 scripts/python/verify_toolchain_workflow_repair.py
```

This runs the registered behavioral tests and compatibility suite, captures
JUnit/stdout/stderr/current source hashes, and appends a fresh directory under
`logs/toolchain-workflow-repair-direct/`. It grants no formal lifecycle state.
Windows includes the existing junction regression; non-Windows explicitly
excludes that one Windows-only case and records Windows verification pending.

### CLI stream encoding

The CLI emits UTF-8 JSON Lines on stdout and UTF-8 diagnostics on stderr,
independent of Windows locale or inherited PYTHONIOENCODING. Subprocess
callers must decode captured output explicitly with encoding="utf-8" and
errors="strict"; text=True alone uses the parent locale and is insufficient.
