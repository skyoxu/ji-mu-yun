# Runner Isolation Contract

## Execution boundary

- **PIWR-015 / FR-010:** `PhaseA.Platform`, platform database, proxy configuration, and deployment assets are platform-owned. User task Runners use a separate low-privilege revocable OS identity and never inherit platform administration or service credentials.
- **PIWR-016 / FR-011:** An Account A Runner cannot read or write Account B Workspace, Snapshot staging, secret directory, or restore output even when application authorization is defective. A real OS-permission negative test is required.
- **PIWR-017 / FR-012:** Server logical identifiers resolve all Workspace, Snapshot, Restore, and Artifact paths. Canonicalization, root containment, traversal, symlink/reparse-point, absolute, UNC, and device-path checks reject escape.
- **PIWR-018 / FR-013:** Runner lifecycle has timeout, cancellation, concurrency, and cleanup bounds. Default is no simultaneous heavy write execution per Project. The contract can evolve to durable lease/fencing rather than a permanent in-process Boolean lock.
- **PIWR-019 / FR-012:** Creation, restore, movement, and platform upgrade validate owner/ACL. Unexpected subjects, broadened access, or inherited permissions isolate the target and block Runner activity until an audited repair succeeds.
- **PIWR-020 / FR-014:** Product isolation claims match evidence. Cross-Account OS isolation is the minimum current claim; same-Project or per-execution stronger isolation is not claimed until supported by its selected profile and evidence.

## Deferred architecture choice

Windows may use local accounts, restricted tokens, Job Objects, NTFS ACLs, or a compatible composition, but this package does not prescribe the mechanism. Architecture must choose OQ-3 identity granularity and document evidence-driven triggers for per-project temporary identity, container, or microVM escalation.

## Required evidence

- **PIWR-A05:** A real low-privilege Runner writes its own authorized Workspace but cannot modify platform binary, SQLite, proxy configuration, or a different Account Workspace.
- **PIWR-A06:** `..`, absolute, UNC/device paths, symlink/reparse points, and escaping manifest paths cannot leave the authorized root.
- **PIWR-A07:** Deliberate ACL expansion or unknown ownership causes isolation/repair and prevents Runner execution.
- **PIWR-A13:** A stale Runner fencing token cannot publish over the current result.
