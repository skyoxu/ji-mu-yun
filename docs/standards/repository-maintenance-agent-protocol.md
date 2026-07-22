# Repository Maintenance Agent Protocol

Status: Active repository standard
Language: English
Scope: Repository-maintenance execution plans and their implementation agents.

## Purpose

This standard defines the durable ownership and authorization boundaries for the Repository Maintenance TDD Adapter. It applies the ownership pattern in Accepted ADR-0041 without redefining Bootstrap Review semantics.

## Three-Layer Ownership

1. `docs/standards/` owns durable normative semantics and authority boundaries.
2. `.agents/skills/quick-dev-tdd-adapter/` owns executable protocol behavior, common schemas, shared validators, and the in-session adapter workflow.
3. Each `execution-plans/<plan>/` owns its implementation-contract instance, plan-specific predicates, fixtures, evidence intent, and immutable evidence references.

Append-only run state, attempt records, result envelopes, and recovery evidence belong under `logs/tdd-adapter/**`, never as mutable execution-plan state.

## Authority Boundaries

- An implementation contract projects numbered plan books; it does not replace their intent or acceptance authority.
- The adapter is stateless and backend-neutral. It cannot schedule providers, commit changes, mark work done, accept candidates, or authorize release.
- Capsules, backend responses, and adapter decisions are observations. Registered predicate results own state transitions.
- Bootstrap Review remains the sole semantic-review authority. Plan-local validation consumes its finalized evidence and owns only the predicate explicitly declared by that plan.
- `plan-ready`, `slice-ready`, `implementation-candidate`, `implementation-accepted`, protected handoff, and release-ready remain distinct states.

## TDD Lifecycle

Each slice binds current authority, contract, validator, command registry, source, and baseline identities before work. It observes an expected RED before production writes, permits minimal GREEN only from current RED evidence, permits REFACTOR only after GREEN, and emits a fresh hash-bound result envelope with explicit authorization exclusions. Any authority, contract, validator, command, write-set, read-set, dependency, or predecessor drift invalidates the run and requires a stale-linked successor.

## Phase Boundary

This protocol does not change Phase A/B APIs, authentication, runtime configuration, Caddy, live metadata, hosted workspaces, shared LLM/Codex entrypoints, or browser behavior. A future slice that consumes a Phase path must additionally satisfy `AGENTS.md`, the relevant Phase ADRs and standards, protected-path approval, compatibility requirements, and targeted tests or smoke evidence.

## References

- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `AGENTS.md`
