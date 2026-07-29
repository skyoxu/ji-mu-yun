# Requirements And Acceptance

This plan preserves the 2026-07-15 requirements document as source authority. It does not paraphrase it into a replacement specification. The source contains `RA-SKILL-001` through `RA-SKILL-073`; S1 must extract those identities atomically and S2 must retain their source hashes, lineage, and matrix mappings.

| Requirement group | Source authority | Slice | Observable acceptance |
| --- | --- | --- | --- |
| Acceptance-first purpose and routing | Sections 1-3; RA-SKILL-021/022 | S1 | The Skill resolves exactly one target, defaults to evidence-only, and does not run Bootstrap or mutate target code without explicit authority. |
| Typed input and content custody | Sections 4, 10; RA-SKILL-015/016/028/055/056/058 | S1/S3 | Run input, baseline/candidate manifests, evidence records, and command invocations are hash-bound, complete-or-explicitly-incomplete, and append-only. |
| Clause inventory and Phase policy | Sections 5-6; RA-SKILL-001/002/003/013/023/026/027/065-073 | S1/S2 | Source partitions, stable check lineage, Phase-only policy activation, exact policy-check coverage, 85 percent changed-line coverage, checklist closure, and scan scope are machine-validated. |
| Phase and DoD calculation | Sections 7-8; RA-SKILL-004/005/006/007/008/014/017/018/062-064 | S2 | Parsed DAG, base matrix, impact projection, typed gates, and distinct First-slice/Phase/Program results reject unauthorized progression. |
| Execution safety and recovery | Sections 10-11; RA-SKILL-011/019/031/032/045/047/059 | S3 | Controlled validation uses typed commands, declared isolated writes, deterministic actions, locks, and stale-linked recovery. |
| Bootstrap collaboration | Section 9; RA-SKILL-012/020/024/025/030/035-044/048-054/060/061/067 | S0/S4 | Bootstrap v2 remains the sole semantic authority; requirement decision, companion capability, Artifact View, import envelope, mapping, approval, and launch authorization are immutable and hash-bound. |
| Package and release candidate | Section 12-13; RA-SKILL-029/033/034/046/057 | S5 | The package has all declared schemas/adapters/policy/commands/CLI, covers positive, negative, mutation, 7-07, pure-Godot, mixed-domain, and fresh-context fixtures, and passes the terminal suite. |

## Non-Negotiable Boundaries

- Code-review conclusions are only for `phase_service`. Pure Godot candidates return `unsupported_code_review_domain`; mixed candidates preserve an `unreviewed_external_domain` partition.
- The Skill never creates a second semantic auditor, Codex runner, Artifact View, gateway, or Bootstrap lifecycle.
- `evidence_only` cannot authorize deterministic or Bootstrap completion. `controlled_validation` requires typed commands and isolated write roots; public command execution resolves only a hash-bound registry entry, Phase scans execute from a hash-verified frozen candidate snapshot, and request input cannot downgrade authority checklist items to optional.
- Bootstrap `clean` cannot replace acceptance inventory, phase gates, DoD, protected gates, or target-plan authority.
- `S5` is only a Skill release candidate. It does not authorize a target plan's protected handoff, release, deployment, or archive.

## Requirement Ledger Rule

`requirements-ledger.v1.json` binds the source file hash and declares all 73 RA IDs as one atomic extraction set. S1 must replace that planned extraction set with a generated immutable inventory; any missing, duplicate, reassigned, split, merged, or tombstoned ID must be represented through the source-defined lineage contract rather than silently renumbered.
