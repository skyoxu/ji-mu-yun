# Repair Round 1 Findings

Source: `docs/know19.txt`. Finalized scope is P0-1, P0-2, P1-1, P1-2, P1-3,
P1-4, and P2-1. P0/P1 findings are repaired in this round; P2-1 is recorded
as a portability follow-up without changing normative authority.

| ID | Disposition | Repair |
| --- | --- | --- |
| P0-1 | fixed | Separate `VCEC-001..036` requirements from `VCEC-A01..A43` acceptances and add complete bidirectional mapping. |
| P0-2 | fixed | Replace prose/range-only validation with registered executable commands and a terminal composition command. |
| P1-1 | fixed | Existing bmad-spec producer is a regression/hardening prerequisite, not a new implementation slice. |
| P1-2 | fixed | Split S3 into S3a semantic handoff, S3b retry/taxonomy, S3c fingerprint/shard, and S3d recovery/context. |
| P1-3 | fixed | Mark the initial source-freeze file as bootstrap planning evidence; formal producer delivery remains S1 acceptance. |
| P1-4 | fixed | Isolate `allow_stale_catalog` as an independently owned control-plane prerequisite with its own tests and regression command. |
| P2-1 | deferred | Durable plan artifacts use repository-relative paths; ephemeral machine paths remain diagnostic only. |
