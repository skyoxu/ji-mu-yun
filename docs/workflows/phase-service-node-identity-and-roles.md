# S2-06 node identity and role boundaries

Authority: [ADR-0061](../adr/ADR-0061-phase-b-c-identity-isolation-workspace-recovery-spine.md),
its scoped 2026-10-28 AD14..26 addendum, and the exact adopted architecture spine.
The original proposed spine labels remain provenance; the later accepted scoped
addendum is the authority. This document grants no live mutation or release.

## Authority before interfaces

The central adapter alone owns current account state, token verification,
initial immutable home and account revision/projection updates. The node consumes
restricted current project/projection/authorization/read-state contracts. Neither
client/project node hints nor diagnostic instance labels select authority.
The same-process boundary is not OS module isolation or a remote protocol.

The following concrete owner/interface/storage handoff is normative design input.
It records the accepted decisions before affected implementation; it is not a
claim that every production consumer has already migrated to restricted objects.

```json
{
  "schema": "s2-06.authority-interface-handoff.v1",
  "source_authority": {
    "adr": "docs/adr/ADR-0061-phase-b-c-identity-isolation-workspace-recovery-spine.md",
    "adopted_spine": "_bmad-output/planning-artifacts/architecture/architecture-s2-06-20261028/ARCHITECTURE-SPINE.md",
    "adopted_spine_sha256": "df6549c9f72595bfd883ea8f3d557935ae0f2daf835b500803618be2ef6ef7f2",
    "decisions": [
      14,
      15,
      16,
      17,
      18,
      19,
      20,
      21,
      22,
      23,
      24,
      25,
      26
    ]
  },
  "ordering": [
    "accepted_irreversible_authority",
    "restricted_interfaces_and_storage",
    "dispatch_implementation",
    "runtime_validation"
  ],
  "central_owner": {
    "path": "PhaseA.Platform/Data/PhaseAMetadataStore.cs",
    "operations": [
      "current_account_state",
      "existing_token_verification",
      "initial_unique_home",
      "account_revision",
      "minimal_projection",
      "central_notice_publication"
    ]
  },
  "node_owner": {
    "paths": [
      "PhaseA.Platform/Program.cs",
      "PhaseA.Platform/Security/RequestContext.cs"
    ],
    "operations": [
      "restricted_project_operations",
      "current_local_authorization",
      "minimal_projection_read",
      "local_notice_read_state"
    ],
    "denied": [
      "central_account_writer",
      "credential_store",
      "sql_connection_or_factory",
      "unrestricted_options",
      "service_locator",
      "home_reassignment"
    ]
  },
  "persistence": {
    "owner": "PhaseA.Platform/Data/SqliteMetadataSchema.cs",
    "database": "existing_protected_local_sqlite",
    "tables": {
      "node_binding": [
        "singleton_key_1",
        "node_id",
        "binding_version",
        "initialization_scope",
        "scheduler_clean_shutdown"
      ],
      "accounts": [
        "home_node_id_nullable_at_install",
        "authority_revision_positive_monotonic"
      ],
      "projects": [
        "node_id_nullable_at_install"
      ],
      "account_node_projections": [
        "account_id_primary_key",
        "home_node_id",
        "is_enabled",
        "authority_revision"
      ]
    },
    "atomic_group": [
      "existing_schema",
      "required_central_admin_initialization",
      "explicit_test_binding",
      "minimal_projection",
      "dirty_start"
    ],
    "conflict": "rollback_entire_binding_increment_without_reassignment_or_adoption"
  },
  "readback": {
    "session": "existing_authenticated_accountId_username_role_plus_ownership",
    "capacity": [
      "nodeId",
      "online",
      "acceptNewAccounts",
      "measurementValid",
      "capacityRef",
      "readinessRef"
    ],
    "unmeasured": [
      false,
      null,
      null
    ],
    "safe_errors": [
      "existing401_authentication_required",
      "existing_safe403_or404",
      "self409_conflict",
      "appropriate503_unavailable",
      "redacted_no_store"
    ]
  },
  "inherited": [
    "ADR-0035",
    "ADR-0036",
    "ADR-0038",
    "ADR-0061_parent_AD1_through_AD13",
    "current_snapshot_package_activation_generation_clarifications"
  ],
  "unresolved_authority_contradictions": [],
  "implementation_claim": "Design handoff only; pending storage/capability/consumer and Windows proof remains explicit.",
  "authorizes": []
}
```

## Installation and refusal

Use the existing local SQLite initializer and one validated additive transaction.
Only explicit single-node test migration may fill legacy null homes/owners.
Existing valid non-null identities, credentials, history and content hashes stay
unchanged. Orphans, invalid registered workspaces and conflicts abort the entire
increment. Fault/restart preserves original facts; no endpoint, project file or
snapshot chooses home. New account/home/projection commits together. A bound home
has no reassignment API. Node and central capabilities stay separate even where
the private trusted adapters share one protected database.

Session and admin home reads use current authenticated identity, with current
central verification and no cross-node private access for administrators.
Old session/auth/error fields remain compatible; ownership fields are additive.
Sensitive readbacks and errors remain no-store and redact protected data.
Online, operator account policy and measurement validity are independent. Until
S2-03A provides real measurement, validity is false and references are null.
No capacity number, placement, higher concurrency, new timeout or run status is
introduced. Entry-only does not create an executable production graph.

## Current implementation and evidence boundary

The first implementation increment adds explicit roles and honest local capacity
readback. Persisted home/projection transactions, complete consumer closure,
fixed-host ownership and all nine AC remain pending until actual code and current
raw test results prove them. Existing broad constructors are not declared safe
merely because a restricted interface or this document exists.

Actual Windows ownership-handle competition, registered low-privilege Runner,
ACL/Job Object and crash-cleanup evidence remain required. Linux metadata/HTTP
and logical registration results cannot supply those proofs. S2-06 test success
cannot open active content or formal accounts without their owning browser,
Identity/password-recovery/minimal-soft-delete/HTTPS conditions. Independent
multi-service/cross-host operation, dynamic placement, test-to-production data or
secret transfer and the later knowledge/notification products remain excluded.

## Local notice adapter boundary

The implemented same-host seam uses the existing trusted `Program` composition
and `PhaseAMetadataStore` backing. Only the entry-role central administrator can
use `CentralNoticePublisher.PublishAsync`; production receives the separate
`NodeNoticeReader` list/detail/unread-count/mark-read contract. Constructors and
backing factories are internal, and ordinary project facades expose neither
publication nor service-provider/SQL access. No new public notification route is
introduced. A supplied node, port, admin field or adapter URL grants no authority.

Publication updates the current protected fact and matching node projection in
one local transaction. Readers revalidate the current central credential and
account/home/projection/local-node chain, then apply current audience, active
revision and UTC validity under the local transaction. Only the authenticated
account/current notice/revision read key can change. A new revision has its own
read state; known expiry and observed withdrawal exclude the old content even
without a future refresh service. A late projection failure rolls back the fact
change and can be retried through the same central operation.

The scoped cases live in `PhaseA.Platform.Tests/NodeIdentity/NodeNoticeTests.cs`
and `tests/s2_06/test_node_notice.py`. Their exact invocation-specific TRX and
native workflow receipts, rather than this description, establish each tested
claim. Full notification product/history/UI, remote increments, cursors and
offline recovery remain with S2-04C/S3-03. Local Linux results do not certify
Windows Runner/ACL/Job Object isolation, cross-host delivery or overall S2-06
completion.
