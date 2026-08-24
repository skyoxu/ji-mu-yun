# ADR-0058: Toolchain Skill Replay Portability and Evaluation Seeds

Status: Accepted

## Context

Historical Skill validation records contain machine-bound validator paths. Future
replays need a repository-owned entrypoint with bounded capability resolution,
detached probes, and non-authorizing receipts.

## Decision

Use `scripts/sc/skill_package_replay.py` with the checked-in capability
descriptor. The descriptor resolves only the declared validator root and the
replay output remains `authorizes: []`. Historical evidence is referenced by
hash and is never rewritten or promoted to a quality baseline.

## Consequences

Compatibility and evaluation artifacts can be replayed on another checkout
while preserving the historical 2026-08-01 bytes and lifecycle ownership.
