# ADR-0045: Bootstrap Verifier Semantic Commit And Recovery

- Status: Accepted
- Date: 2026-07-25

## Context

ADR-0041 makes process events authoritative and requires failed Codex attempts to leave formal reviewer and verifier evidence unchanged. The repository runner validated verifier output against its JSON Schema before writing `verifier-output.json`, but deferred blocker evidence and context-coverage validation until `finalize`.

A schema-valid verifier response could therefore become formal output and receive an `attempt-completed` event even though `validate_verifier(...)` would later reject it. The completed operation and non-empty formal output then prohibited another verifier attempt. Gate could not be rerun, finalization could not succeed, and the operator guide offered no append-only recovery path for the already-recorded execution defect.

## Decision

Bootstrap verifier output uses semantic commit-before-publish and an explicit append-only recovery lane.

- The parent control plane validates every verifier candidate with `validate_verifier(...)` against the frozen gate blocker set before atomically replacing `verifier-output.json`.
- Both newly generated verifier prompts and the Codex runtime wrapper derive every blocker's full inclusive evidence range and complete `contextRead` set from the frozen candidate sidecar. The runtime wrapper therefore remains complete when recovering a legacy prompt that exposed only a finding start line.
- Schema, binding, exact finding-evidence coverage, and every `contextRead` reference are all pre-publication requirements. A failure records an `attempt-failed` event and preserves the existing formal output bytes.
- After semantic validation and immediately before replacing formal verifier output, the parent revalidates the frozen launch authority. Authority drift records `attempt-failed`, preserves the prior formal bytes, and never appends `attempt-completed`.
- `recover-verifier` is the only supported recovery command for a completed, semantically invalid Codex verifier output. It is available only to an active, non-finalized, non-sealed `codex-exec` run whose gate is `awaiting_verification`.
- Recovery is rejected when the current verifier output passes semantic validation, when no completed verifier operation exists, or when a verifier attempt is active.
- The command copies the exact rejected formal bytes into a unique `verifier-recoveries/<recovery-id>/` directory, writes a schema-valid hash-bound recovery record, and appends a `verifier-recovery-opened` process event. It does not clear or rewrite the rejected formal output.
- The recovery event changes only the derived verifier lease state and reopens one retry lane. Reservation remains allowed while the recovery is open only if the current formal output still matches the archived rejected hash.
- A later semantically valid verifier publication plus `attempt-completed` closes the recovery. Finalization and finalized-run validation reject an open, missing, stale, or invalid recovery lineage.
- Recovery evidence has `authorizes=[]` and grants no finding acceptance, plan acceptance, implementation acceptance, protected handoff, commit, release, or done authority.

This decision extends ADR-0041. It does not supersede ADR-0041 or change the three-layer review model, verifier independence, provider routing, review-round limits, or plan-local acceptance authority.

## Consequences

- Semantic verifier defects are retryable without deleting process history or hand-editing formal evidence.
- A failed retry leaves both the rejected legacy output and the new failed attempt evidence available for audit.
- `inspect-run` can distinguish an unrecovered invalid completion from an open recovery and a valid completed verifier.
- The control plane gains one generic recovery Schema and targeted regression coverage.
- Historical runs without recovery events remain valid under the existing lifecycle contract.

## References

- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `docs/standards/bootstrap-review-control-plane.md`
- `.agents/skills/run-phase-bootstrap-review/SKILL.md`
- `.agents/skills/run-phase-bootstrap-review/schemas/bootstrap-verifier-recovery.v1.schema.json`
