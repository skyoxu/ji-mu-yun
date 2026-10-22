# Skill Authoring Standard: Package A

Current VDD state: **plan-ready**, native compiler publication for the complete
Package A scope. The prior native Quick Dev run completed all 31 slices and
published implementation-complete/pass. ADR-0062 and standard version 1.0 were
formally adopted by the maintainer on 2026-10-22. Current-runtime evidence refresh is complete: 31 slices and 578 closure tuples
passed native Q7/Q8 and Acceptance handoff readback on 2026-10-22. Formal
Acceptance is owned by [the current pointer](acceptance-current.v1.json); its
absence or a non-passed result is not acceptance-passed.

- Branch: `fix/08-06-skill-authoring-plan-refresh`.
- Current plan: `package-a-completion-plan/semantic-plan-bundle.v1.json`.
- Plan ID: `PLAN-D6248F18A869`.
- Plan semantic SHA-256: `35e43f85da4a14b5c8554be8b66d9977d4356b664f04dc77c6685ffb5ee1e6f5`.
- Coverage: 289 active obligations, 289 Acceptances, 300 exact coverage edges,
  31 slices. Requirement source bytes remain unchanged.

## Start here

1. [requirements.md](requirements.md): authoritative Package A source.
2. [LOCAL-HANDOFF.md](LOCAL-HANDOFF.md): current compilation result, local/online
   routes, completed slice boundaries and next action.
3. [Completion handoff](ONLINE-COMPLETION-2026-10-21.md): full-scope implementation
   evidence and refresh status.
4. [Historical dependency atomic repair](repair/2026-10-20-dependency-atomic/README.md):
   earlier split, compiler fixes, historical S3 evidence and limits.
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
historical. Use `package-a-completion-plan/`, never the root historical implementation contract.
`dependency-atomic-plan-03/` and earlier completion descriptions are historical.
