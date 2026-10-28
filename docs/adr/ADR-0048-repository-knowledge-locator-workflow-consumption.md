# ADR-0048: Repository Knowledge Locator Workflow Consumption

- Status: Accepted
- Date: 2026-07-26

## Context

Repository-maintenance workflows need a consistent way to locate current
repository knowledge without promoting a search index, a caller prompt, or an
LLM response into source authority. The completed knowledge context plan
defines the projection boundary, while VDD, Quick Dev, and Bootstrap Review
need a narrow repository-local consumption contract.

## Decision

- Repository source and Accepted ADRs remain fact authority. Knowledge
  projections and indexes are `derived_cache` only.
- A deterministic Locator returns source locations, hashes, provenance,
  ranking evidence, and confidence status. It does not return synthesized fact
  answers and callers must reread and hash-verify recommended sources.
- Trusted workflow adapters own the domain, path, snapshot, budget, and
  confidence envelope. A caller LLM may provide untrusted query intent but
  cannot widen that envelope.
- VDD records accepted or rejected consumption decisions after reread. A
  rejected candidate cannot satisfy a required knowledge module; an uncovered
  required module blocks plan readiness.
- Quick Dev consumes only VDD-frozen accepted decisions. Bootstrap Review may
  locate context before prepare, then freezes accepted context in its Artifact
  View. Neither may expand context after its respective freeze point.
- Locator ambiguity fallback is disabled by default. When an approved policy
  enables it, Python code delegates only through
  `scripts/sc/_llm_backend.py::run_llm_exec`.
- Repository-fact maintenance pins local `refs/heads/main`, performs no
  implicit fetch, checkout, merge, or branch mutation, and records only
  derived artifacts and append-only maintenance evidence.

## Relationships

### Administrator-operated BMAD reader (2026-10-27)

The `bmad-planning` identity is a read-only consumer for administrator-operated
PRD, SPEC and Architecture sessions. It may locate every otherwise eligible
published repository-source module, including conditional and historical
content, without an additional document/code category restriction. Existing
source exclusions, snapshot, publication and source-hash checks still apply.
This identity grants no knowledge maintenance, write or publication authority
and is not an authentication mechanism. Device access remains administrator
controlled. Native BMAD and repository wrappers remain unchanged; local
customization may invoke the real outer-repository Locator from private runs.
A branch-only policy does not activate this reader before authorized
main-bound publication.

This ADR **Extends ADR-0044** for repository-local deterministic knowledge
consumption.

This ADR **Complements ADR-0037, ADR-0041, and ADR-0043**. ADR-0037 remains
the shared LLM/Codex entrypoint authority. ADR-0041 remains the Bootstrap
Review control-plane authority. ADR-0043 remains the VDD clarification and
recovery authority.

This ADR **does not supersede** ADR-0037, ADR-0041, ADR-0043, or ADR-0044.

## Consequences

- Consumers share one deterministic location-only retrieval core and stable
  contracts instead of independently searching or synthesizing answers.
- Missing, stale, low-confidence, out-of-policy, or hash-drifted results fail
  closed according to the trusted consumer policy.
- This decision does not authorize Phase routes, Hosted E2 dispatch changes,
  live metadata access, deployment, acceptance, handoff, release, or commit.

## References

- `docs/adr/ADR-0044-knowledge-projection-authority-e2-hosted-context-envelope.md`
- `docs/adr/ADR-0037-phase-shared-llm-codex-entrypoints.md`
- `docs/adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md`
- `docs/adr/ADR-0043-vdd-solo-maintainer-clarification-recovery.md`
- `execution-plans/2026-07-26-knowledge-locator-workflow-integration/`


## Applicability amendment: ordinary planning advice (2026-10-23)

This repository-owner entry records the applicability distinction in the
approved BMAD/VDD knowledge-query architecture, AD-9, before implementing its
new ordinary-planning integration. It does not assert that the integration,
Windows verification, or implementation Acceptance has completed.

- Ordinary PRD, SPEC, Architecture and VDD planning may use bounded, read-only
  Locator advice independently of formal knowledge governance. Query results
  remain locations and diagnostics; callers verify actual source bytes and
  own their consumption decisions.
- Preserve explicit governance option > environment > phase precedence.
  An absent phase remains development, and auto remains off in development.
  Ordinary advice creates no frozen knowledge, Skill-input attestation,
  authorization, review lineage or governance package.
- When formal governance is enabled, the original required-module, source
  integrity, freeze and authorization gates still apply. An advisory hit,
  fallback source read or new diagnostic never satisfies or waives them.
  Quick Dev's existing frozen-context consumption boundary is unchanged.
- Only positively identified absence, timeout, inconclusive matching or
  permitted source drift may use the approved independent-source-check path.
  Invalid requests/configuration, damaged publication bindings, denied paths
  or policy, and unidentified failures remain fail-closed. Necessary facts
  that remain unverified block the dependent judgment.
- Keep ADR-0044, ADR-0050, ADR-0057 and ADR-0059 permission, publication and
  self-change rules. Neither querying nor recovery publishes a generation.
  First publication for the new consumer remains a separate maintainer action
  through the existing owner after implementation verification and main merge.
- The planning-query interface is external adaptation. Existing Locator
  fields, status meanings and exit semantics remain unchanged; native BMAD
  files, typed SPEC ownership and formal Acceptance ownership remain intact.

The normative detail is the approved canonical SPEC's behavior-contracts.md
and failure-modes.md, with its adopted architecture AD-6 through AD-10. Future
budget or authority changes must return to their existing owners; this entry
adds no new freeze, service, permission or completion authority.

## 2026-10-28 applicability: citation materialization

Normative inputs and explicit required scope remain mandatory read sources. A
prose citation alone is not a request to append its excerpt to every planning
query delivery. The adapter retains safe existing citations as reference-only
path/hash/mention metadata, includes those bytes in the existing UTF-8 budget,
and binds them to episode content identity. A consumer must read and verify a
reference before factual adoption. Selected Locator evidence retains its actual
read set. Path denials, publication integrity, candidate authorization, closed
episodes, cumulative accounting, the 4096-byte reserve and existing hard ceiling
remain unchanged. Blocked and exhausted results withhold reference metadata.
This is a bounded producer/consumer clarification, not new lookup permission or
a persistent reference cache.
