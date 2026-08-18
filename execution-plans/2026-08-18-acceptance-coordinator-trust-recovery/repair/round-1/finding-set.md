# Repair Round 1 Finding Set

Predecessor: `868328c827a814f9042fdfa62c52ab574a424b24`

This bounded repair addresses only the current plan-contract defects:

- terminal runner argument and predicate incompatibility;
- missing final receipt bindings;
- requirement/slice and acceptance-ID traceability;
- self-hosted input and authority declarations;
- accidental write access to the immutable 2026-08-17 plan;
- contamination of the new RED baseline by behavior already present at the
  plan creation commit.

It does not modify the 2026-08-17 plan, its authorization, terminal, resume
state, report, or historical evidence.

The shared workflow changes present in predecessor commit `f6a9191b`
(`scripts/python/skill_input_consumption.py`,
`scripts/python/launch_skill_input_consumer.py`, and the matching test) are
recorded as a pre-existing candidate delta. They are outside this plan's
slice write-sets and are not evidence of this plan's RED/GREEN execution.
They require separate workflow-repair ownership or explicit VDD disposition
before this plan can publish `plan-ready`.

The predecessor review input is also bound explicitly as
`docs/know58.txt` with content hash
`sha256:75def4c0c62f45bce45cdc660087bedb88b353d2e456829cdd74ac1d37f37e07`.
It is an attached finding source, not lifecycle authority or completion
evidence.

`repair-closure.json` is intentionally absent until the targeted validation and
the maintainer-owned authority prerequisites are complete.
