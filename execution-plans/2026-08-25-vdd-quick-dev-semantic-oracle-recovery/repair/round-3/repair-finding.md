# Repair Round 3 Finding

- Trigger: `high_risk_boundary_changed`
- Baseline candidate: `6a987bfcb9c998820bcbed61fceadf61503a78c4`
- Affected slices: S5 and downstream S6
- Preserved completed slices: S1-S4
- Failure: `build_run_inputs.py` publishes the predecessor freeze file hash while `artifact_owners.py` requires the bound S3 process-receipt hash, so S5 GREEN deterministically fails with `PROMOTION-PREDECESSOR-JUDGE-UNBOUND`.
- Contract gap: `execution-plans/2026-08-25-vdd-quick-dev-semantic-oracle-recovery/tools/build_run_inputs.py` is not in the S5 production write set.
- Bounded repair: add that path to the S5 production owner/read/snapshot sets and preserve only S1-S4 results bound to the predecessor contract. S5/S6 remain invalidated.
- Historical evidence: the failed S5 GREEN run remains immutable and non-promotable.
