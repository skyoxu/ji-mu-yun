# Requirements and Acceptance Preservation Map

## FR preservation

| PRD requirement | PIWR obligations | Canonical location |
| --- | --- | --- |
| FR-001 Identity terminology | PIWR-001 | identity-and-ownership.md |
| FR-002 Server identity resolution | PIWR-002 | identity-and-ownership.md |
| FR-003 Production identity direction | PIWR-003 | SPEC.md, identity-and-ownership.md |
| FR-004 Revocable credentials | PIWR-004 | identity-and-ownership.md |
| FR-005 Disablement and role change | PIWR-005..007 | SPEC.md, identity-and-ownership.md |
| FR-006 Administration and retention | PIWR-008 | identity-and-ownership.md |
| FR-007 Resource ownership | PIWR-009, PIWR-012 | identity-and-ownership.md |
| FR-008 Unified authorization | PIWR-010..011 | identity-and-ownership.md |
| FR-009 Private response and secret protection | PIWR-013..014 | identity-and-ownership.md |
| FR-010 Platform/Runner separation | PIWR-015 | runner-isolation.md |
| FR-011 Cross-Account OS isolation | PIWR-016 | runner-isolation.md |
| FR-012 Safe paths and ACL | PIWR-017, PIWR-019 | runner-isolation.md |
| FR-013 Runner lifecycle | PIWR-018, PIWR-038 | runner-isolation.md, api-evolution-and-operations.md |
| FR-014 Isolation-level transparency | PIWR-020 | runner-isolation.md |
| FR-015 Workspace identity and storage | PIWR-021..022 | workspace-recovery-contract.md |
| FR-016 Versioned Snapshot | PIWR-023 | workspace-recovery-contract.md |
| FR-017 Snapshot boundary | PIWR-024 | SPEC.md, workspace-recovery-contract.md |
| FR-018 Restore Attempt | PIWR-025 | workspace-recovery-contract.md |
| FR-019 Validate before publication | PIWR-026 | workspace-recovery-contract.md |
| FR-020 Environment rebuild and re-entry | PIWR-027..028 | workspace-recovery-contract.md |
| FR-021 File authority and hosted route compatibility | PIWR-029..030 | SPEC.md, workspace-recovery-contract.md |
| FR-022 Retention and substitute-root drill | PIWR-031..032 | workspace-recovery-contract.md |
| FR-023 Async state | PIWR-033 | api-evolution-and-operations.md |
| FR-024 Compatibility and bounded failure | PIWR-034..035 | api-evolution-and-operations.md |
| FR-025 Browser consumes server decisions | PIWR-036 | api-evolution-and-operations.md |
| FR-026 Placement/migration compatibility | PIWR-037, PIWR-039..040 | api-evolution-and-operations.md |

## NFR preservation

| NFR | Canonical location |
| --- | --- |
| NFR-001 Fail closed | SPEC.md, api-evolution-and-operations.md |
| NFR-002 Security and data minimization | identity-and-ownership.md, api-evolution-and-operations.md |
| NFR-003 Consistency and idempotency | workspace-recovery-contract.md, api-evolution-and-operations.md |
| NFR-004 Compatibility | identity-and-ownership.md, api-evolution-and-operations.md |
| NFR-005 Recoverability | workspace-recovery-contract.md, SPEC.md |
| NFR-006 Observability | api-evolution-and-operations.md |

## Acceptance contract

| ID | Required falsifiable result | Covers |
| --- | --- | --- |
| PIWR-A01 | Client account override cannot alter server Principal/Account; protected entries deny consistently. | PIWR-001, 002, 010, 036 |
| PIWR-A02 | Revoked credential, disabled Account, and insufficient admin role deny without stale cache/session bypass. | PIWR-004..008, 013 |
| PIWR-A03 | Cross-Account Project/Run/Artifact/Snapshot/Restore/Preview enumeration denies without information leak. | PIWR-009..011 |
| PIWR-A04 | Fresh, upgraded, and reused DB preserve data; orphan/conflicting ownership is not auto-assigned. | PIWR-009, 012, 034 |
| PIWR-A05 | Low-privilege Runner can write its Workspace and cannot write platform or other Account resources. | PIWR-015, 016, 020 |
| PIWR-A06 | Traversal, absolute/UNC/device paths, symlink/reparse points, and manifest escape fail containment. | PIWR-017, 023, 026 |
| PIWR-A07 | ACL is verified after create/restore/move; drift isolates and blocks Runner. | PIWR-019, 026 |
| PIWR-A08 | Snapshot/log/artifact secret scan excludes tokens, provider keys, temporary tickets, absolute paths, and prohibited content. | PIWR-014, 023, 024, 027 |
| PIWR-A09 | Standard Workspace restores at a new root with content, ACL, route/readback, and controlled Run verification. | PIWR-021..024, 026, 030, 032 |
| PIWR-A10 | Wrong tenant, corrupt hash, unknown schema, quota, and incompatibility fail before publication. | PIWR-023, 025, 026, 035 |
| PIWR-A11 | Injected stage exits recover by continue/rollback/isolate from Attempt/staging state. | PIWR-025, 028, 029 |
| PIWR-A12 | Old preview ticket/port/PID/secret/lease is invalid; current environment state is rebuilt. | PIWR-027, 030, 037..039 |
| PIWR-A13 | Duplicate idempotency key cannot publish two Workspaces; stale fencing cannot overwrite current. | PIWR-018, 025, 038 |
| PIWR-A14 | Retention, pin, quota, deletion, and failed-staging cleanup are audited and protect active inputs. | PIWR-031, 033, 035 |
| PIWR-A15 | Private API is no-store with bounded redacted responses. | PIWR-013, 033..035 |
| PIWR-A16 | Optional topology fields retain one-node behavior; Restore does not depend on nodeId or absolute path. | PIWR-021, 034, 037..039 |
| PIWR-A17 | API authorization positive/negative evidence is present; React E2E follows React baseline. | PIWR-010, 033, 036 |
| PIWR-A18 | New-process evidence package covers isolation, permissions, round-trip, fault, DB upgrade, and redaction. | PIWR-001..040 |

## Deferred and resolved product choices

| Source question | Canonical disposition |
| --- | --- |
| PIWR-Q01 Account meaning | Resolved: Account is Tenant; one-to-one user compatibility is temporary. |
| PIWR-Q02 Production identity | Resolved direction: OIDC-first; provider/session design deferred to Architecture. |
| PIWR-Q03 Disable/delete/retention | Resolved current scope: disablement and immediate revocation; physical purge deferred. Retention duration remains OQ-4. |
| PIWR-Q04 OS identity granularity | Open OQ-3 for Architecture. |
| PIWR-Q05 Snapshot content | Resolved boundary in `workspace-recovery-contract.md`; representative fixture fixed in the operations profile. |
| PIWR-Q06 Retention/quota/encryption/RPO/RTO | Open OQ-4 for Spec/Architecture operations profile. |
| PIWR-Q07 React timing | Resolved: deferred and non-blocking for backend closure. |

## Wrapper-only content

- The upstream PRD review rubric and both upstream/downstream memlogs are process records, not canonical sources or companion authority.
- The requirements document's suggested BMAD sequencing and external-reference narrative are absorbed only insofar as they impose scope, non-goals, or current-contract constraints; they do not authorize implementation or introduce external runtime dependencies.
