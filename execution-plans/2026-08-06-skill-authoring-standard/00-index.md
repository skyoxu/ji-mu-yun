# Skill Authoring Standard: Package A

Current VDD state: **plan-ready** (native compiler publication, 2026-10-20).
Implementation has started through the native online Quick Dev route. S3 has
current slice-ready evidence; Package A implementation and Acceptance remain
incomplete. First-use entry preparation is available under ADR-0041.

- Branch: `fix/08-06-skill-authoring-plan-refresh`.
- Current plan: `dependency-atomic-plan-03/semantic-plan-bundle.v1.json`.
  `current-plan/` is the immutable published predecessor, not the current entry.
- Plan ID: `PLAN-D6248F18A869`.
- Plan semantic SHA-256: `7d90d6df1513cc4a6b232493e7da06e69151266a0202c91cf850e1141cdd7af0`.
- Coverage: 289 active obligations, 289 Acceptances, 299 exact coverage edges,
  25 slices; zero source gaps or invented obligations.
- Source bytes and all 25 product intent rows remain unchanged by this online repair.

## Start here

1. [requirements.md](requirements.md): authoritative Package A source.
2. [LOCAL-HANDOFF.md](LOCAL-HANDOFF.md): current compilation result, local/online
   routes, completed slice boundaries and next action.
3. [Online repair report](repair/2026-10-20/online-repair.md): changes, verification
   and exact evidence paths.
4. [Dependency atomic repair](repair/2026-10-20-dependency-atomic/README.md):
   source-bound split, compiler fixes, current S3 evidence and limits.
5. [Earlier reconciliation](repair/2026-10-18/reconciliation.md): original SAS
   coverage and exclusions.

## Scope and authority

Package A covers the Skill authoring standard, deterministic static package
validator, fixtures and migration guidance. It does not implement Package B,
knowledge query changes, Phase services, Bootstrap/internal review, or runtime
capability enforcement. Completed 8-05 and 8-24 remain the baseline.

The three Skill online-route changes are separately authorized maintenance in
this branch. The compiled Package A write set does not authorize changing those
Skills. Only `scripts/vdd/compile_plan.py` published this plan. Online responses
were actual host-authored worker inputs; native schema, source, semantic,
feasibility, chain and handoff gates decided publication.

## Historical records

Historical v1 contracts, plan-local tools, old statuses and earlier repair records
are not current execution authority. The previous navigation and handoff text
are retained under `repair/2026-10-20/`. Earlier failed compiler attempts remain
historical. Use `dependency-atomic-plan-03/`, never the root historical implementation contract.
