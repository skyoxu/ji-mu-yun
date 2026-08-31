# Adversarial architecture review — 2026-08-31 (r17)

Target: the frozen `ARCHITECTURE-SPINE.md`, SPEC companions, the
`architecture-decision-registry.v1.json` artifact, and the plan-local tools
named by the spine. This pass attacks the current revision with two
independently implemented adapters and rechecks AD-13, AD-15, AD-17, and
AD-21. The spine was not modified.

## Gate verdict

**PASS for architecture convergence; AD-15 implementation handoff BLOCKED.**
No remaining document-level divergence was found. Q8, closure tuple identity,
typed snapshot roots/Git delta, governance-artifact exclusion, and decision
registry bindings are mutually consistent. The only failures are known
brownfield implementation deviations explicitly classified by AD-15.

## AD-15 implementation findings

### H1 — Legacy combined receipt/observation writer

`execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/artifact_owners.py:78-110`
still executes the SUT, constructs the process receipt, invokes the judge, and
writes observation/classification through one authority. This fails the AD-15
diagnostic row (a). It must be migrated to executor-only immutable receipt
write followed by independent judge-only observation/classification before
implementation handoff.

### H2 — Legacy lifecycle bypasses the descriptor/executor seam

`tools/stage_command.py:26-30,61-79` still launches direct pytest/owner
subprocesses, uses divergent cwd roots, and pre-writes terminal observation;
the lifecycle registry still lacks an authoritative RED descriptor. This fails
AD-15 rows (d) and (e). Direct probes must remain diagnostic-only and their
outputs must be rejected by lifecycle predicates until one descriptor-bound
executor path is proven.

### H3 — Legacy validator does not consume typed snapshot/closure contracts

`tools/validate_all.py:16-20,55-57` still derives a Git status/index summary
and selected-manifest digest rather than invoking the versioned
`current-snapshot-manifest.v1` resolver and validating AD-19 closure tuples at
Q0/Q4/Q7/Q8/recovery. This fails AD-15 rows (c) and (g), leaving current
candidate and runtime closure unenforced in the implementation.

## Closed architecture checks

- Q8 uses `runtime_closure_tuples` with canonical `tuple_key` in
  `execution-protocol.md`, `schema-contracts.md`, and
  `implementation-contracts.md`; exact V6A tuple cardinality is consistent.
- Snapshot manifest uses the exact eight runtime root kinds (governance
  registries/memlog/spine/review/authorization excluded), canonical POSIX path
  grammar, typed Git additions/deletions/renames, and plan-state exception in
  both schema companions.
- `architecture-decision-registry.v1.json` exists with 21 AD entries and
  selection/spine bindings; recomputed hashes match the referenced bytes.
- AD-13 runtime-resolved launcher/version policy, AD-17 resolver contract,
  governance exclusion, trust boundaries, artifact ownership, Mermaid graphs,
  and Deferred entries are mutually consistent.
- `lint_spine.py`: PASS, zero findings.

## Recommendation

Architecture may proceed as a converged build substrate. Keep implementation
handoff gated by AD-15 until H1–H3 are remediated and a fresh conformance run
records those rows as `pass`; do not alter CAP scope or weaken the truth floor.
