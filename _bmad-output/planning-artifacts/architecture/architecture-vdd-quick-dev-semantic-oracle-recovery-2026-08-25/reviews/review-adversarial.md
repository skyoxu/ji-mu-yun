# Adversarial Review

## Verdict

Changes required before the spine is finalized: the layered result contract is
not yet a closed legal-combination contract, so independently built executor,
coverage, and recovery components could diverge at the completion boundary.

## High

1. `AD-6` permits too much through underspecification. It lists some invalid
   combinations but does not define the complete admissible tuple set for
   `evidence_state`, `verification_outcome`, `failure_family`, and
   `failure_id`. In particular it does not state whether `pass` can carry
   `expected-red`, when a `failure_family` is required for `blocked` or
   `incomplete`, or whether `not-applicable` permits a failure identity.
   Define the legal combinations positively and make all omitted tuples
   invalid.

2. `recovered-run` is not sufficiently constrained. A validated predecessor
   observation with matching identities could be replayed as completion
   evidence without expressly requiring the referenced immutable receipt and
   observation to remain admissible, current under the change-impact policy,
   and revalidated by the coverage gate. State that recovery only references
   existing evidence; it never synthesizes an observation or receipt, and is
   ineligible after any required rerun/invalidation.

3. The active Acceptance ID universe has no explicit authoritative input.
   `AD-5` requires every active ID to be covered, but the graph/rules only
   identify VDD's per-oracle `covers_acceptance_ids`. Require VDD semantic
   intent to bind a verified active-ID manifest (or immutable reference to the
   authoritative plan contract) so coverage cannot silently treat its own
   subset as the universe.

## Medium

1. The component graph makes `acceptance-coverage` appear to feed recovery
   directly (`C --> RA`) while `AD-3` says Quick Dev is the recovery artifact's
   sole writer. Label this as a read dependency into Quick Dev, then show
   Quick Dev publishing the recovery artifact. This removes any implication
   that the coverage gate writes recovery data.

2. `AD-4` says the executor/judge derives every `failure_family` and
   `failure_id`, although coverage failures such as uncovered Acceptance IDs
   originate at the coverage gate. Partition classification ownership by
   artifact: executor classifications belong in observations; coverage gate
   classifications belong in coverage artifacts; Quick Dev classifications
   belong in recommendation/recovery artifacts. Preserve the single-writer
   rule while avoiding a false cross-zone dependency.

## Validation

`lint_spine.py --workspace ...architecture-vdd-quick-dev-semantic-oracle-recovery-2026-08-25` passed with zero findings. The issues above are semantic boundary gaps beyond that structural lint.
