# Adversarial architecture review — 2026-08-31 (r10)

Target: the frozen `ARCHITECTURE-SPINE.md`, normative SPEC companions, and
the plan-local brownfield tools named by the spine. This pass specifically
rechecks AD-19 (typed runtime closure), AD-20 (typed snapshot roots/Git delta),
and AD-21 (memlog decision identity). The spine was not modified.

## Gate verdict

**BLOCKED.** AD-19–AD-21 are present in the rendered spine and memlog text,
but the companion schemas and implementation remain behind those decisions.
The same inputs can still be accepted with different closure grouping and
snapshot semantics, while the registered execution path continues to violate
the split-writer and descriptor/executor boundaries.

## High findings

### H1 — AD-19 is not wired into `terminal_input`

`implementation-contracts.md:391-405` still requires only
`assertion_edge_refs: string[]`; it does not require the typed
`runtime_closure_tuples[]` set introduced by AD-19. Although a standalone
`runtime_closure_tuple` definition exists at lines 457-468, no terminal input
field references it and no closed-set schema enforces one tuple for every
V6A `(slice_id, acceptance_id, stage)`. A validator grouping by assertion,
Acceptance, or slice can therefore disagree while remaining schema-valid.
Make the typed tuple array required, reject duplicate/missing/extra tuples, and
bind each tuple's edge/hash/selector/current-snapshot to the terminal input.

### H2 — AD-20 prose conflicts with the snapshot schema

AD-20 requires `current-snapshot-manifest.v1` to contain typed root entries
with `root_kind`, normalized repository-relative path, content hash, source
commit, and inclusion reason, plus typed Git additions/deletions/renames. The
actual `current_snapshot_manifest` schema (`implementation-contracts.md:423-440`)
still exposes nine free-form string properties (`candidate_tree`, `plan`,
etc.), an untyped `excluded_roots` array, and no delta object. Consequently two
resolvers can hash different bytes or classify unknown/renamed paths
differently while both satisfy the companion. Replace the legacy shape with
the AD-20 root-entry and delta schemas and make the old shape read-only
compatibility input.

### H3 — AD-21 registry is declared but absent from the memlog and schema

The architecture `.memlog.md:46-48` adds AD-19/20/21 as plain decision text;
there is no immutable decision-identity registry mapping historical ordinals
to AD IDs, and no schema/record for that registry. Earlier ownership entries
remain unlabelled, so `supersedes: AD-6` and `supersedes: AD-15` cannot identify
the replacing decision deterministically. A resume can still select a
historical entry by position. Add and validate a closed append-only registry
artifact; fail closed on missing, duplicate, or contradictory live identities.

### H4 — Brownfield execution still violates the declared authority seams

`execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/artifact_owners.py:78-110`
executes the process, constructs the receipt, invokes the judge, and writes
combined evidence. `tools/stage_command.py:26-30,61-79` directly launches
pytest/owner commands and pre-writes terminal observation. The registry has no
authoritative RED entry. These paths violate AD-3/AD-4/AD-15 even though the
spine now records the intended split-writer model; implementation handoff
remains blocked until executor-only receipt, judge-only observation, and one
descriptor-bound seam are demonstrated in a fresh run.

### H5 — Write-set and Git-delta enforcement is not executable in the current tools

The slice schema still models `allowed_write_paths`, `execution_snapshot_paths`
and `planned_new_files` as unconstrained string arrays, and the active
`validate_all.py` compares a selected manifest/status summary rather than the
AD-20 typed additions/deletions/renames set. Symlink/junction containment and
unknown-path invalidation are therefore not proven for every process-bearing
stage. A successor can add an unlisted file under an allowed directory and
remain accepted by the current implementation.

## Medium findings

### M1 — Detached bundle fields do not encode outside-candidate/import isolation

The detached bundle schema has path strings, hashes, and booleans but no
machine predicate that paths are outside the candidate tree or that the bundle
cannot import candidate evidence writers. AD-18 remains partly prose-only.

### M2 — Runtime edge result hash remains weakly typed

`runtime_assertion_edge.result_sha256` is still a free-form string while other
hashes require `sha256:<64 hex>`, allowing inconsistent identity normalization.

## Closed checks

- AD-19/20/21 intent is visible in spine and memlog: **PASS in prose**;
  machine-contract and implementation closure: **FAIL** (H1–H5).
- V5→V6→V6A ordering and plan/runtime edge separation: **PASS**.
- Selector identity reuse and layered outcome/failure model: **PASS in
  principle**.
- `lint_spine.py`: **PASS**, zero findings.

## Recommendation

Keep architecture status `draft` and block handoff. Wire AD-19–AD-21 into
closed companion schemas and the resolver, fix the legacy executor/judge and
stage seams, then rerun the full Reviewer Gate on a newly frozen revision.

