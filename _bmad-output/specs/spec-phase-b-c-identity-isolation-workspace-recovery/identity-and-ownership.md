# Identity and Ownership Contract

## Authority model

| Boundary | Required authority | Must not own |
| --- | --- | --- |
| Browser / React client | User intent and display of server decisions | Account identity, ownership, role, Runner identity, or recovery validity |
| Phase service | Authentication, authorization, Account/Project ownership, scheduling, metadata, audit, restore orchestration | Long-running user-code environment or browser-supplied identity truth |
| Sandbox / Runner | Restricted execution and controlled Workspace file operations | Account lifecycle, product authorization, or cross-project scheduling |
| Agent Runtime | Bounded model/coding work in the sandbox | Product identity, Run, Workspace, manifest, recovery, or business authority |

## Identity and credential obligations

- **PIWR-001 / FR-001:** `Principal`, `Account/Tenant`, `Member`, `Role`, and `Credential/Session` are distinct. A one-account-one-user prototype mapping is explicitly temporary compatibility.
- **PIWR-002 / FR-002:** The server derives Principal, Account, and Role from verified credential plus server relations. Browser `accountId`, hidden fields, route parameters, and local storage only select a requested target and never replace the authenticated context.
- **PIWR-003 / FR-003:** Human production identity follows OIDC-first. Existing administrator bearer tokens are bootstrap, migration, or controlled service credentials; a self-built password system requires an explicit future product decision.
- **PIWR-004 / FR-004:** Every bearer token, session, and service credential has stable identity, scope, creation, last-use, expiry/revocation status, and secure derived storage. Rotation invalidates its predecessor; the control-plane cache window is at most five seconds and protected entry points revalidate current state.
- **PIWR-005 / FR-005:** Disabled Accounts block new Run, Restore, Preview, and private-resource activity after the bounded five-second control-plane window. Existing atomic work may finish, then is drained or cancelled; no new write lease or publication is granted.
- **PIWR-006 / FR-005:** Role changes invalidate or re-evaluate capabilities without relying on stale client state.
- **PIWR-007 / FR-006:** Administrator actions use independent authentication, authorization, and audit.
- **PIWR-008 / FR-006:** Reversible disablement and immediate revocation are current behavior. Physical deletion/purge is deferred, asynchronous, retention-aware, and explicitly confirmed.

## Ownership, isolation, and confidentiality

- **PIWR-009 / FR-007:** Project, Run, Artifact, Package, Asset, Chat, Workflow, LLM usage, Workspace, Snapshot, Restore Attempt, and Preview have server-controlled Account/Project ownership. Orphaned or conflicting records do not auto-adopt to the requester.
- Project deletion is a server-owned soft-delete marker; deleted projects are excluded from ordinary user lists and new operations, retain auditable ownership, and release logical quota without immediate physical deletion.
- **PIWR-010 / FR-008:** Every protected API, background operation, and data access applies Account/Project authorization.
- **PIWR-011 / FR-008:** Cross-account ID enumeration for Project, Run, Artifact, Snapshot, Restore, and Preview is uniformly denied without target existence, path, or Account disclosure.
- **PIWR-012 / FR-007 and NFR-004:** Fresh DB, upgrade DB, and reused DB retain valid data and give old ownership records deterministic compatibility interpretation.
- **PIWR-013 / FR-009:** Private API responses use no-store semantics; browser-facing status/error values are bounded and do not expose raw exceptions or secrets.
- **PIWR-014 / FR-009 and NFR-002:** Provider keys, temporary tokens, and secrets are injected only for authorized Run/Runner lifetime; they cannot enter Snapshot manifests, restore manifests, browser-readable responses, ordinary artifacts, or raw command logs. Detectable cleanup failure blocks reuse.

## Required evidence

- **PIWR-A01:** Browser attempts to submit another `accountId` cannot alter server Principal/Account; protected entries deny consistently.
- **PIWR-A02:** Revoked credentials, disabled Accounts, and administrator-role failures deny without old-cache/session bypass.
- **PIWR-A03:** Cross-account resource enumeration denies without information leak.
- **PIWR-A04:** Fresh, upgrade, and reused DB cases preserve valid data and refuse automatic ownership adoption.
- **PIWR-A15:** Private API no-store and bounded redacted error behavior hold.
- **PIWR-A17:** Authorization positive and negative API evidence exists; later React E2E is not a current closure substitute.
