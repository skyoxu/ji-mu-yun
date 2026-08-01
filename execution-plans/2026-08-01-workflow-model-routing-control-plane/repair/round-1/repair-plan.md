# Repair Round 1 - Acceptance Prerequisite Extension

## Blocker

Refactor Acceptance originally rejected this compact VDD target because it had
no full implementation contract, no toolchain code-review policy, and no
complete prerequisite projection. The prerequisite extension is implemented
under `execution-plans/2026-08-01-refactor-acceptance-toolchain-compact-vdd/`.

## Candidate Continuity

Acceptance evaluates the original model-routing implementation together with
the prerequisite extension required to review it. The original target remains
the lineage owner. Candidate scope is an explicit sorted list and is never
inferred from the dirty worktree.

`acceptance_core.py` was already dirty before either implementation and later
received the toolchain extension. Its pre-extension bytes are reconstructed by
`tools/materialize_acceptance_core_baseline.py`, which performs exact one-time
replacements and must reproduce the frozen SHA-256
`91e795353f0df8e19433753fb355e9a95fd0eadf891685ceddf213cba02fe4a9`.

This repair authorizes no Acceptance, Bootstrap, release, or archive state.

## Acceptance Action Recovery

The first persisted Acceptance action proved that the plan validator still
compared the live candidate bytes with the pre-overlap dirty hash. The validator
now permits that one declared path to drift only when the plan-owned overlay
exists and reproduces the frozen hash exactly. All other dirty bindings retain
their original byte-equality rule.
