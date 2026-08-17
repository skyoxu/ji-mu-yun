# Quick Dev TDD Stage Recovery

## Purpose

Replace the adapter's one-process `RED -> GREEN -> REFACTOR` execution with
resumable, evidence-gated stage transitions. This plan absorbs Chapter 6's
stage and recovery semantics without importing its task format, scripts, logs,
or business-repository dependency.

## Scope

- Adapter-owned stage summaries and candidate binding.
- Route-first continuation across RED, implementation, GREEN, refactor, and
  terminal validation.
- Legacy one-shot run evidence remains readable but cannot publish new-stage
  evidence.
- 8-17 is the first dogfood consumer after this plan completes.

## Non-Goals

- No Bootstrap invocation, lifecycle ownership change, daemon, scheduler, or
  Chapter 6 runtime dependency.
- No modification of Phase service, runtime, user sandbox, or Knowledge
  authority.

## Required Order

`S0 -> S1 -> S2 -> terminal-full`

The migration bridge may create only each slice's declared test file before
RED. Production changes remain prohibited until that RED observation exists.
