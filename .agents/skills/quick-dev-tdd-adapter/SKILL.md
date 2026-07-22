---
name: quick-dev-tdd-adapter
description: Execute one hash-bound Repository Maintenance TDD slice through prepare, observed RED, minimal GREEN, refactor, and evidence capture.
---

# Repository Maintenance TDD Adapter

Use this Skill only with a valid `implementation-contract.v1.json` and a named behavior slice. It is a stateless, in-session protocol adapter; it is not a provider scheduler, review authority, commit authority, or release authority.

## Target Plan Report Lifecycle

Complete this lifecycle before `prepare` or any implementation identity freeze:

1. Read `execution-plans/95-implementation-report-index.v1.json` and look up the exact target plan directory. Do not enumerate or recursively scan other execution-plan directories.
2. On an index hit, require exactly one matching entry, require its `report_filename` to be a basename matching `95-*.md`, and verify that the resolved file exists inside the indexed target directory.
3. On an index miss, inspect only the named target directory. If one `95-*.md` already exists, use it and register its complete filename. If none exists, create `95-implementation-evolution-and-completion-report.md` and register it. Create the report and update the index in the same pre-implementation change, preserving unrelated entries and deterministic directory ordering.
4. A duplicate, stale, escaping, or ambiguous entry fails closed and routes to VDD repair. The index is a non-authoritative path hint; the target report remains append-only continuity documentation and cannot authorize acceptance, commit, handoff, release, or completion.
5. Audit the target plan, route material defects through the VDD repair write gate, append the pre-implementation change entry to the resolved report, validate the repaired plan, and refreeze every affected identity before observing RED.

After the target plan's current declared terminal predicate passes, append its overall implementation result to the same report. Never use report text or an index entry to satisfy that predicate.

## Required Order

1. Read the current plan contract, authority sources, predecessor evidence, and the three references in this Skill.
2. Freeze the current plan, source, contract, validator, command-registry, Git baseline, and write-boundary identities.
3. Run the declared RED command and require its expected nonzero failure before a production write.
4. Make only the minimal allowed GREEN change, then run the declared GREEN command.
5. Run the declared REFACTOR checks and emit current, append-only evidence under `logs/tdd-adapter/**`.

The adapter never treats backend text, a Capsule, an adapter decision, a clean process exit, or this Skill as acceptance authority. Only the plan-local registered predicate may authorize its declared state.

## Boundaries

- Use structured command descriptors with `shell: false`; do not accept raw shell commands.
- Reject authority, command, validator, contract, write-set, read-set, dependency, baseline, or predecessor drift.
- Preserve failed evidence and create a stale-linked successor instead of overwriting a run.
- Do not invoke Stock BMAD Quick Dev as an authoritative backend or consume its review/done state.

Read [implementation-backend-contract.md](references/implementation-backend-contract.md), [tdd-run-protocol.md](references/tdd-run-protocol.md), and [evidence-and-freshness.md](references/evidence-and-freshness.md) before implementing a slice.
