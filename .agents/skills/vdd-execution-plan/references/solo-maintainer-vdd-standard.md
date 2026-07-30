# Solo-Maintainer VDD Standard

Verification-driven planning means a plan names observable behavior, current validation commands, and the distinct lifecycle state those commands support. It does not require a proof system larger than the change.

## Required Controls

- Route one standalone requirements Markdown file to direct implementation. Enter VDD `create` or `repair` only for an explicit request concerning a complete execution-plan directory.
- Preserve the repository-owned Skill and plan-local authority boundary accepted in `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`; this routing does not grant Bootstrap or acceptance authority.
- Follow the optional clarification recovery and sensitive quarantine boundary accepted in `docs/adr/ADR-0043-vdd-solo-maintainer-clarification-recovery.md`.
- Preserve repository instructions, UTF-8, path containment, protected-path approval, sensitive-data minimization, current Git identity, and additive historical evidence.
- Select `standard`, `resumable`, or `self-hosted` before choosing plan artifacts.
- Keep intent, scope, non-goals, authority, implementation slices, RED/negative or legacy-regression evidence, targeted validation, and one terminal full validation actionable.
- Do not equate plan readiness, implementation authorization, implementation completion, acceptance, or archive.
- Use existing repository validators first. Add a schema, validator, fixture, ledger, or generated view only when a named machine consumer changes a routing or validation decision.

## Freshness And Repair

Use Git baseline/range or a scoped dirty-worktree identity. Bind current contracts, implementation, and validation inputs, but exclude append-only reports and logs. Preserve previous evidence as historical rather than rewriting it.

Repairs first run the smallest targeted checks for the affected layer. A local slice change invalidates only that slice and declared downstream dependents. One final full replay follows stabilization; replay all slices only after a shared lifecycle contract, global validator semantic, baseline identity, or all-slice dependency changes.

Repairs stay in the original execution-plan directory by default. Append
`repair/round-<n>/` with the finalized finding set, predecessor identity,
bounded repair slices, and hash-bound closure. Validators must accept ordered
repair rounds without rewriting completed initial slices. A successor requires
an explicit supersede or incompatible-scope decision.

If Bootstrap implementation review is selected, record one stable lineage family derived from the original plan target and retain it across in-place
repairs and successor history for that target. The default full-review budget is two semantic rounds and the hard limit is three. A successor never resets
the budget. Round 3 is allowed only for a new P0/P1 finding, an authority or
context graph change, or a high-risk boundary change; after the hard limit,
route to manual pause.
Require a current hash-bound inspect-lineage projection even for zero consumed rounds; a missing projection must fail closed instead of opening Round 1.
Legacy pre-family history is bridged only by an explicit lineage-adoption
record bound to an Accepted policy authority and exact historical run hashes.

Each P0/P1 repair re-entry includes a generated root-cause callsite inventory
that disposes every discovered sibling as changed or explicitly excluded. It
also includes a successful controlled producer/consumer composition receipt.
The repair changed set comes from hash-bound complete baseline/candidate
manifests, and the receipt binds the current bytes of every producer and
consumer input.
The repair delta names changed files, direct consumers, targeted tests, and
validation references. When two rounds are consumed and no Round 3 trigger
exists, use deterministic closure rather than another complete review.
Bind every present changed path to its content hash and every deleted path to an explicit tombstone.
Each composition check covers a changed path, uses declared direct consumers, and exposes its receipt as a validation reference.

Review scope is the smallest complete consumer closure. Name explicit changed
files, direct consumers, targeted tests, plan authority, standards, repository
rules, and current acceptance evidence. Do not use a whole source, test, Skill,
document, log, or plan directory merely because it contains one relevant file;
a directory scope needs an explicit minimal-closure attestation.

Codex process failure, malformed child JSON, and an invalid Artifact View
receipt are transport attempt failures. Retry the same role in the same run;
they consume no semantic round and create no successor lineage. P2-only results
use current-run disposition and targeted deterministic closure, never an
automatic complete semantic review.

## Optional Controls

`resumable` adds compact state and a 95 report only for cross-session or dependent work. `self-hosted` adds only protocol fixtures and migration checks consumed by workflow-control changes. Filesystem edge fixtures, recovery ledgers, review, Bootstrap evidence, external trust roots, signatures, verifier separation, and distributed publication are not defaults.

Optional clarification state is one atomic, single-writer current file. Current decisions have one material classification and an acyclic dependency list. Hash drift is observed without mutation; invalidate and reopen are explicit. Legacy bytes are inspected only against a caller-supplied digest, and sensitive current state is replaced by a sanitized terminal quarantine envelope.

If two repair cycles add plan-control fields without new observable behavior, stop and simplify or split the control-plane scope. If historical evidence did not occur, choose revalidation, affected-slice replay, full replay, or historical-only retention; never fabricate it.
