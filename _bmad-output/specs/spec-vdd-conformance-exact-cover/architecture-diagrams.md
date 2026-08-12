# Architecture Diagrams

## Canonical Flow

```text
Canonical Spec Package（owner: bmad-spec）
        ↓
VDD source-freeze producer
        ↓
vdd-source-freeze-manifest.v1
        ↓
VDD create / repair
        ↓
Exact-cover deterministic preflight
        ├─ deterministic failure → typed family/action
        │                            ↓
        │                  VDD/source-freeze repair
        ↓
run aggregate fingerprint + shard reuse fingerprints
        ↓
obligation extraction shards
        ├─ unchanged clean → safe reuse
        ├─ unstable → bounded jitter diagnostics → hotspot/quarantine
        └─ stable/changed → deterministic canonicalization
                                  ↓
                        deterministic exact-cover
                                  ├─ blocked → typed repair → rerun
                                  ├─ requirement_semantic_review_required
                                  │     ↓ explicit authorization
                                  │ Bootstrap bootstrap-upstream-plan
                                  │     ↓ validation envelope
                                  │ VDD repair → exact-cover rerun
                                  └─ conformant + authorizes=[]
                                        ↓
                                prerequisite satisfied
                                        ↓
                                existing implementation
                                authorization owner
```

## Lifecycle Separation

```text
Pre-implementation requirement ambiguity
exact-cover
  → requirement_semantic_review_required
  → explicit authorization
  → Bootstrap bootstrap-upstream-plan
  → validation envelope
  → explicit VDD repair
  → exact-cover rerun

Post-implementation semantic assurance
implementation-complete
  → Refactor Acceptance
  → decide-bootstrap
  → Bootstrap implementation/focused profile
```
