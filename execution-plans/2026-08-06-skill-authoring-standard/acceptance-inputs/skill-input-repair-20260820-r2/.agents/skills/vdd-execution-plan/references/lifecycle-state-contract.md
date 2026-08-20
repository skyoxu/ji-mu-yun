# Lifecycle State Contract

The static machine-readable owner is [lifecycle-state-contract.json](lifecycle-state-contract.json). Every new plan uses:

`draft -> plan-ready -> implementation-authorized -> implementation-complete -> acceptance-passed -> archived`

VDD owns `draft` and `plan-ready`. The maintainer may explicitly publish `implementation-authorized` after the plan is actionable; Bootstrap Review is optional supplemental evidence and cannot publish a lifecycle state. Quick Dev may publish only `implementation-complete`, after terminal full validation. The implementation acceptance Skill owns `acceptance-passed`; the archive Skill owns `archived`.

Old state names are accepted only by the compatibility adapter for repair of existing plans and are never emitted. No transition implies a later transition. An authorization override never implies acceptance, handoff, release, or archive.
