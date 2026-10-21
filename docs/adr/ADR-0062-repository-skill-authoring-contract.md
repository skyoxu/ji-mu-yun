# ADR-0062: Repository Skill Authoring Contract

Status: Proposed; maintainer adoption is required before final acceptance.
Date: 2026-10-21. Governing accepted decision: ADR-0041.

## Context

Package A needs one deterministic, capability-aware local declaration standard.
The completed 8-05/8-24 owners already enforce execution/evidence and platform
isolation; static package declarations cannot replace those owners.

## Proposed decision

Adopt docs/standards/skill-authoring-standard.md version 1.0, the policy and
versioned contract/result schemas, and the read-only validate_skill_quality.py
API/CLI. Enforce A01--A25 and the fewer-than-500 logical-line boundary. Resolve
policy/schema inputs inside repository_root and content references inside the
selected package, without executing commands or fetching remote sources.
Retain existing owner-specific protocols. Return deterministic bounded sanitized
JSON with empty authorizes and local pass/fail/error/legacy exit semantics.

Package B migrates the five existing Skill packages later; Package A neither
changes those Skills nor requires their compliance as a gate. Bootstrap Review
remains optional. VDD, Quick Dev, Acceptance and Knowledge retain their current
authorities. No Phase runtime, live credentials, new Runner, OIDC, knowledge
publication or internal reviewer is introduced.

## Consequences and verification

Static checks prove declarations and controlled fixture outcomes only. They do
not establish OS/network/restore enforcement or arbitrary prose semantics.
Verify the real Python entry and public CLI with the four Package A test modules,
including boundary, mutation, no-side-effect, migration and parity cases. Native
Quick Dev Q7/Q8 and Acceptance retain completion authority. Existing accepted
ADR-0041 governs development while this decision remains proposed.

## Adoption

No accepted status or maintainer approval is inferred from passing tests. Record
the actual maintainer adoption decision here before final Package A acceptance.
