# Risks, Definition Of Done And Glossary

## Risks

| Risk | Mitigation | Blocking condition |
| --- | --- | --- |
| Projection becomes instruction authority | Derived-cache labels, source reread and trust fixtures | Any projection authority claim |
| Contract duplication with ADR-0037/0038 | ADR-0044 relationship and existing-contract aggregate | Missing or conflicting reference |
| Seeder copies generated knowledge cache | Host-owned cache root and K7 Seeder policy evidence | Cache under repository/workspace |
| Inventory misses a caller | Source-generated snapshot and direct-call scan | Source/inventory drift or unknown reachability |
| E2 overclaims isolation | Explicit E2/E3 boundary and readiness revocation | Any filesystem-isolation claim in E2 |
| LLM ambiguity classification bypasses shared backend | K5 static guard for `run_llm_exec` | Direct provider or Codex invocation |
| Caller LLM controls authority or scope | Split intent from trusted envelope and validate owner | `owner=llm` or hint expands allowed Domain |
| Locator becomes an answer generator | Closed result Schema and generated-answer negative fixture | Free-form fact answer in Locator output |
| Untargeted maintenance expands the corpus | Existing-only closed-world fixture | New/candidate entry without target |
| Worktree content becomes repository fact | Pinned local-main authority and provisional status | Worktree source marked main-backed |
| Maintenance edits its consumer | Zero source-mutation contract and append-only evidence | Any inspected source or consumer write |
| Review runs before executable artifacts exist | Bootstrap entry gate and plan-local validator | Missing Schema/fixture/ledger/validator |

## Plan-ready DoD

- ADR-0044 exists with Accepted status and is listed in the Phase ADR index.
- Original requirements are hash-bound and remain unchanged as input.
- All required plan-local artifacts exist and parse.
- Positive and negative fixtures pass targeted expectations.
- Inventory generator reproduces checked-in snapshots from the current source.
- Every active requirement maps to a slice, acceptance ref, and source evidence.
- Locator and maintenance request/result Schemas exist, and every indexed interface fixture returns its exact expected outcome.
- ADR-0044 and the original requirements agree on local-main authority, caller/LLM input ownership, source-location-only results, and maintenance write boundaries.
- K0-K10 and K11-K13 production write policies are mechanically checked.
- Whole-directory validator passes and publishes only `plan-ready`.
- Bootstrap Review is still supplemental and not run by this DoD.

## Glossary

- `E1`: Retrieval-scoped, experimental Projection and evaluation.
- `E2`: Parent-assembled, run-bound Context Envelope enforced at shared Hosted entrypoints.
- `E3`: OS/worker filesystem, process, network and secret isolation; separate Phase C scope.
- `Projection`: A derived cache that never has instruction authority.
- `Lifecycle Instance`: Repository Source, Repository Template, Project Instance or Run Artifact View.
- `Context Envelope`: Signed, run-bound manifest aggregating existing Hosted contracts and assembled artifacts.
- `BH-HANDOFF`: The protected handoff required by the paused frontend-boundary plan.
- `plan-local`: An artifact inside this execution-plan directory or its synthetic evidence path, not production code.
- `Knowledge Locator`: The single deterministic retrieval core that returns source locations and ranking evidence, not a fact answer.
- `consumer_ref`: An optional repository-relative object boundary read directly by the Locator instead of being summarized by a caller LLM.
- `existing-only`: Closed-world maintenance over source entries already registered in the knowledge snapshot.
- `targeted`: Maintenance whose discovery is bounded by one explicit consumer object; target-only worktree content remains provisional.
