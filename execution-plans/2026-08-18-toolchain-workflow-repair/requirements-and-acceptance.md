# Toolchain Workflow Repair Requirements

## Purpose

Repair the repository toolchain orchestration so fast repository evolution
does not turn stale context or transport mechanics into accidental hard gates.
The repair must preserve authority ownership and must not publish Knowledge
authority automatically.

## W0 / TWR-W0: Typed Source Selection

Source selection must be represented by typed consumer, policy, module,
resource-set, authority, and path/module identifiers. Consumers must not infer
the source universe from filename exclusion lists. The projected read set and
its selection identity must be independently verifiable.

Acceptance `TWR-W0-EXIT`: equivalent selections produce the same canonical
selection identity; omitted, ambiguous, or authority-drifting selections fail
closed.

## W1 / TWR-W1: Transport Planning

The adapter owns chunking, pagination, continuation offsets, and bounded retry
planning. The model does not decide whether a source was truncated. Every
continuation binds to the same source selection and current source identity.

Acceptance `TWR-W1-EXIT`: a large source is transferred through deterministic
pages to complete coverage; a stale or conflicting continuation is rejected.

## W2 / TWR-W2: Adapter-owned Coverage

Coverage is computed from observed byte/line ranges and source hashes by the
adapter. A complete result is marked complete only after the adapter proves
coverage. Model-visible summaries are evidence, not coverage authority.

Acceptance `TWR-W2-EXIT`: missing ranges, overlapping conflicting pages, and
source-byte changes produce typed failures or controlled refreshes; the model
cannot promote an incomplete read to complete.

## W3 / TWR-W3: Knowledge Three-gate Model

Knowledge controls must distinguish:

1. execution gate: whether the current verified context is usable;
2. publication gate: whether a new Knowledge authority may be published;
3. review gate: whether semantic review is required for a Knowledge-system
   change or authority/selection drift.

Catalog staleness or same-selection source-byte drift may produce a controlled
successor context and degraded execution. Invalid LKG, selection drift,
authority drift, missing required sources, or publication-integrity failure
must retain their typed blocking behavior. Acceptance never publishes
Knowledge authority, and Bootstrap is not started automatically.

Acceptance `TWR-W3-EXIT`: execution can continue with a verified degraded
successor when semantics are unchanged; publication and semantic-review gates
remain independently enforced.

## Ownership

VDD owns draft and plan-ready. Maintainer owns implementation authorization.
Quick Dev owns implementation-complete. Acceptance owns acceptance-passed.
The shared workflow repair does not create a new lifecycle authority.
