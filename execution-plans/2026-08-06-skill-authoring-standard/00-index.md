# Skill Authoring Standard: Package A

Current VDD state: **plan-ready** (native compiler publication, 2026-10-20).
Implementation and acceptance have not run. The first-use Quick Dev limitation
below remains open; plan-ready does not mean immediate implementation readiness.

- Branch: `fix/08-06-skill-authoring-plan-refresh`.
- Current plan: `current-plan/semantic-plan-bundle.v1.json`.
- Plan ID: `PLAN-D6248F18A869`.
- Plan semantic SHA-256: `c647f2711e31dde964c81efa466cd9ec5235998b0c63fecc4e64dad55ff6b057`.
- Coverage: 286 active obligations, 286 Acceptances, 297 exact coverage edges,
  25 slices; zero source gaps or invented obligations.
- Source bytes and all 25 product intent rows remain unchanged by this online repair.

## Start here

1. [requirements.md](requirements.md): authoritative Package A source.
2. [LOCAL-HANDOFF.md](LOCAL-HANDOFF.md): current compilation result, local/online
   routes, first-use blocker and next action.
3. [Online repair report](repair/2026-10-20/online-repair.md): changes, verification
   and exact evidence paths.
4. [Earlier reconciliation](repair/2026-10-18/reconciliation.md): original SAS
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
historical. Use `current-plan/`, never the root historical implementation contract.
