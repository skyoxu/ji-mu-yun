# Validators, Fixtures And Control Gates

## Validation layers

The plan-local validator runs the following order:

1. Parse every JSON artifact as strict UTF-8 JSON and reject non-finite constants.
2. Check every declared Schema has a Draft 2020-12 identity, required fields, and closed root shape.
3. Validate plan state, implementation contract, requirements ledger, fixture index, inventory envelopes, and source provenance.
4. Validate every Context Envelope and knowledge-interface positive/negative fixture against the same family-specific Schema and semantic checks.
5. Rebuild the synthetic JCS/HMAC reference vector, validate the full envelope Schema, and recompute canonical bytes, SHA-256, and HMAC-SHA-256.
6. Rebuild the three caller inventories in a temporary directory and compare bytes with the checked-in inventory snapshots.
7. Check Locator trusted-field ownership, request/result source and path-policy identity, recommended-path containment, status/confidence/read-set consistency, exact ranks/anchors, and mandatory hash revalidation.
8. Check maintenance mode/target consistency, request/before-snapshot identity, local-main pinning, closed-world discovery, provisional worktree status, zero source mutation, LKG disposition, and append-only logging.
9. Check cross-artifact identities, slice references, acceptance-reference uniqueness, source snapshot identity, and protected-path policy.
10. Publish `plan-ready` only when all checks pass and no production-code or live-workspace action is requested.

## Positive fixtures

Positive fixtures must prove that a valid project-bound envelope, account-bound envelope, non-prompt route disposition, optional budget omission, and a valid inventory snapshot can pass the composition rules.

Knowledge-interface positives additionally prove an LLM-authored query with adapter-owned trusted fields, direct `consumer_ref` routing, `insufficient_match`, existing-only refresh, and targeted provisional worktree handling.

## Negative fixtures

Negative fixtures must target one primary failure, including permission expansion, cross-project source, stale snapshot, unknown policy, modified signed payload, replayed nonce, required budget omission, recovery-order mismatch, missing source-boundary disposition, E2 paired with a non-enforce gate, cache-root escape, and inventory source drift. The validator must report the declared failure code, not merely `invalid`.

Knowledge-interface negatives additionally target LLM-owned authority, generated answers, source or path-policy drift, paths outside the trusted policy, matched low confidence, request/before-snapshot mismatch, untargeted discovery, worktree fact promotion, consumer/source mutation, dirty-worktree authority, implicit fetch, and non-append logging.

## Gate modes

`legacy`, `observe`, and `enforce` are server policy values. The plan-local validator accepts all three as baseline data but never declares E2 readiness for `legacy` or `observe`. A client-supplied gate mode is invalid. Production code cannot consume these artifacts until the BH-HANDOFF or merge/supersede gate is satisfied.

## Deterministic preflight

The terminal command is:

```text
py -3 execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/validate_whole_directory.py --publish-plan-ready
```

This command is plan-local and read-only except for the plan-local `plan-state.v1.json` status update from `draft` to `plan-ready` after all checks pass. It never edits production code, live state, historical evidence, or the standalone original requirements file.
