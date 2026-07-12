# Global Review And Split Validation

## Purpose

Prevent missing books, broken links, authority duplication, uncovered requirements and top-level re-expansion.

## Required Validator

BH-HANDOFF must run a deterministic validator whose executable/workflow, bootstrap rules and mutation fixtures were frozen and signed before the handoff-only task existed. The task cannot add or modify it. Entry:

```powershell
& $env:PHASE_BOUNDARY_HANDOFF_VERIFIER verify-plan --repo C:\jimuyun --bootstrap-contract <signed-contract-path>
```

`PHASE_BOUNDARY_HANDOFF_VERIFIER` resolves only from protected host/workflow configuration and its binary/workflow digest must match BootstrapHandoffContract. A repository script, PR-provided executable or task-modified verifier is invalid.

It validates:

- exact required book set from `00-index.md`
- top-level recovery metadata and links
- every relative link
- required headings per book
- top-level plan remains an index and stays under an approved size threshold
- one owner book per normative requirement family
- no duplicate upstream route/status/action/readback/UI vocabulary definitions
- every active `PBR-*` ledger entry maps to exactly one owner book, exactly one valid implementation phase, acceptance and test/evidence intent
- every original-plan section maps in `98-original-to-split-audit.md`
- `99-source-coverage.md` covers every owner book and post-split ledger entry
- no orphan/superseded book is still linked as authority
- every normalized pre-fourth and accepted fourth/fifth/sixth/seventh-review finding appears exactly once in its coverage table and maps to one or more appropriate `PBR-*` entries with owner book and phase assignment
- BootstrapHandoffContract schema/canonicalization/signature/verifier/lock/launcher-inventory/registry/custody/allowlist hashes match the externally signed frozen values
- UpstreamHandoffManifest contains the exact final upstream commit, zero-unresolved-finding Phase 0A/0B/1-6/global-review closure and the existing upstream fixture/standards/compatibility refs promised by that plan
- HandoffSourceMap classifies every field as `upstream_committed`, `upstream_exit_evidence` or `downstream_derived`; derived frontend/API/persistence snapshots retain source hashes and cannot claim upstream authority
- immutable manifest, append-only state events and protected transactional ActiveRegistry have at most one active handoff/epoch, exactly one at BH-HANDOFF successful exit, and valid atomic replacement/CAS/event ancestry; partial or gap transitions cannot become authoritative
- two UpstreamCompletionSnapshot captures use the same signed schema/allowlist hash, final commit and handoff lock and contain zero active upstream task/run/lease/process, dirty upstream path or claimed-path overlap rows
- before BH-HANDOFF exit, exactly one handoff-only task may be active and every changed path is append-only handoff evidence or the protected ActiveRegistry CAS; validator/tests/plan/spec and implementation paths remain unchanged
- no downstream implementation task/path is active while an upstream task/path is active or dirty
- no downstream surface/action/status/route/readback/diagnostic/UI/schema/standards owner duplicates an upstream handoff owner
- every React derived surface/API observation, Work Policy action, route evidence ref, persistence observation and standards section resolves to the same handoff ID/hash
- downstream-owned standards changes form a valid DownstreamStandardsDeltaManifest chain without changing upstream-owned section hashes
- fifth/sixth/seventh-review finding coverage is complete
- superseded PBR rows resolve through the explicit Requirement Status Registry; prose alone cannot change active status
- top-level recovery uses active handoff finalCommit and contains no authoritative static Git Head

The validator runs at BH-HANDOFF, on every later change to the top-level plan/split directory, and at every phase exit. Its mutation suite deliberately changes the validator/rule digest, modifies plan/spec during handoff, weakens the external lock, omits a launcher, removes a source-map row, converts a derived snapshot into upstream authority, creates two active registry rows, injects a partial state-event/registry transaction, breaks event ancestry, leaves a P0/P1/P2 finding unresolved, changes one UpstreamCompletionSnapshot capture, adds a non-allowlisted path, rebinds an invalidated task, bypasses either Platform or Hosted BH-SF1 go/no-go, breaks PBR status/supersession or introduces top-level phase aliases; every mutation must fail with a stable rule ID.

## Authority Families

| Requirement family | Owner book |
| --- | --- |
| Threat model/Gates | 01 |
| Permit/attestation/verifier/Authority | 02 |
| Profiles/Preflight/network/tool containment | 03 |
| Work Policy/lease/journal/acceptance/quarantine/side effects | 04 |
| React/auth/session/CSRF/build/migration/rollback | 05 |
| Platform architecture/Data/correlation/version/DB compatibility | 06 |
| Evidence/telemetry/retention/capacity/performance | 07 |
| Execution phases/task sizing | 08 |
| Risks/DoD/glossary | 09 |
| Review/validation | 96 |
| Post-split requirements | 97 |
| Historical split mapping | 98 |
| Coverage assertion | 99 |

## Global Review Inputs

- top-level plan and all books
- upstream GDD-to-module index/standards/ADRs
- `97-post-split-requirements-ledger.md`
- `98-original-to-split-audit.md`
- `99-source-coverage.md`
- implementation diff, tests and evidence when reviewing a phase exit
- BootstrapHandoffContract, immutable UpstreamHandoffManifest/source map/derived snapshots, state-event chain, active registry, upstream final commit and referenced upstream Phase/global/closure evidence

## Review Method

1. Verify BH-HANDOFF and run validator.
2. Verify owner-book and cross-plan authority uniqueness.
3. Review P0/P1/P2 findings against actual implementation, not plan prose.
4. Check protected trust-boundary changes with external verifier evidence.
5. Check Postflight actual diff binding.
6. Check durable rules migrated to standards/ADR/workflow.
7. Record immutable review result under stable evidence path.

## Acceptance

- Validator fails on a deliberately removed book, broken link, duplicate owner or missing ledger coverage.
- Validator is operational at BH-HANDOFF before BH-SF0A task creation and every later phase-exit evidence records its result/version and handoff hash.
- Top-level plan cannot silently receive detailed normative sections without validator failure/review.
- Global review has zero unresolved P0/P1; P2 requires owner/expiry/recheck.
