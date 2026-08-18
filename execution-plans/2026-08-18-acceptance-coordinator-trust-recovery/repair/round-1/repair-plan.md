# Repair Round 1 Plan

## Scope

1. Align the implementation contract with the requirements and acceptance IDs.
2. Separate legacy RED regression from the 8-17 read-only dogfood.
3. Make the plan-local terminal predicate consume the Quick Dev invocation
   contract and emit a hash-bound result.
4. Add the self-hosted resume, Skill-input, Knowledge, and authority
   prerequisites without fabricating receipts.
5. Rebase RED intent on behavior not already present at `868328c8`.

## Validation Order

1. Run the explicit Skill-input repair gate for this target plan.
2. Obtain acceptance of ADR-0058 (persisted coordinator evidence ownership)
   and ADR-0059 (Knowledge degraded successor/publication separation), or
   replace them with narrower Accepted decisions.
   The non-authorizing request is recorded at
   `architecture-acceptance-request.v1.json`; its decision hashes must be
   revalidated before any acceptance transition.
3. Generate and validate Knowledge context and freeze artifacts.
4. Validate the repaired contract, registry, terminal runner, and targeted
   fixtures.
5. Only then publish `plan-ready`; Quick Dev owns all RED observations.

## Non-goals

- No Bootstrap invocation.
- No Knowledge publication from this plan.
- No modification of the 2026-08-17 historical plan.
- No release, deployment, archive, or lifecycle authorization.
