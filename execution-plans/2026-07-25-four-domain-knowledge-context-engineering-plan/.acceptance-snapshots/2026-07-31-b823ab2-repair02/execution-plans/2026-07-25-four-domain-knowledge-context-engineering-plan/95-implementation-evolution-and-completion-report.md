# Knowledge Context Plan Implementation Evolution And Completion Report

Status: Pre-implementation; plan-local directory creation only.

This report is append-only and non-authorizing. It does not publish `plan-ready`, implementation authorization, implementation completion, acceptance, handoff, release, or archive.

## 2026-07-25: Initial directory creation

- Input: `execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan.md`.
- Decision: use the `resumable` VDD profile because K0-K14 are dependent and cross-session.
- Decision: add ADR-0044 rather than modifying ADR-0037 or ADR-0038.
- Safety: no Phase production code, live metadata DB, live Hosted workspace, runtime, provider, or Bootstrap Review was touched.
- Pending: run plan-local composition validator and publish `plan-ready` only from current evidence.

Later implementation and validation events must be appended with the current source snapshot, command, output hash, affected slice, and recovery disposition.

## 2026-07-25: Plan-local executable specification completed

- Decision authority: Accepted ADR-0044 extends ADR-0037, complements ADR-0038, and supersedes neither.
- Materialized: 10 closed-root Schemas, 18 indexed positive/negative fixtures, 40 active requirements, K0-K14 slice contracts, five inventory/snapshot outputs, a source scanner, a composition validator, and six plan-local tests.
- Inventory command: `py -3 execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/build_hosted_inventory.py`.
- Inventory evidence: source snapshot `73725b0574274f7ec99e6ffd5763b04e42aebf10fc294985eecb5947fa69df52`; observed source-derived caller counts were 9 Codex Hosted, 18 LLM route engine, and 11 Python backend callsites; direct violations were zero. These counts are evidence, not contract constants.
- Preflight command: `py -3 -B execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/validate_whole_directory.py`.
- Preflight result: PASS at `draft`; `implementation_authorized=false`; `bootstrap_review_started=false`.
- Affected slice: plan authoring only; K0 has not started.
- Recovery disposition: none required after two validator-detected contract repairs; no failure evidence was rewritten.
- Safety: no Phase production code, tests, runtime, live metadata DB, live Hosted workspace, provider, or Bootstrap Review was touched.

## 2026-07-25: Plan-ready published

- Terminal command: `py -3 -B execution-plans/2026-07-25-four-domain-knowledge-context-engineering-plan/tools/validate_whole_directory.py --publish-plan-ready`.
- Result: PASS; lifecycle state is `plan-ready` and `authorizes=["plan-ready"]`.
- Explicit exclusions: implementation authorization, K0 execution, protected-path writes, BH-HANDOFF, acceptance, release, archive, and Bootstrap Review remain ungranted.
- Recovery disposition: re-run the read-only whole-directory validator after this append-only report entry; invalidate `plan-ready` if any normative artifact or source snapshot drifts.

## 2026-07-25: Nested contracts and signature vector strengthened

- Trigger: content review found that the first Manifest Schema closed only its root and omitted per-domain visibility plus several signed execution-policy fields.
- Repair: close nested requirement, snapshot, inventory, fixture, context-assembly, and Manifest objects; add project/account/platform identity branches and the complete three-part envelope.
- Added executable evidence: `context-envelope-reference-vector.v1.schema.json`, a generated synthetic JCS/HMAC vector, and canonicalization/tamper tests.
- Correction to the earlier materialization entry: the current set is 11 Schemas, 18 indexed semantic fixtures plus one reference vector, and eight plan-local tests. The earlier 10/18/six observation is historical pre-strengthening evidence.
- Reference-vector payload SHA-256: `91d2a209fb0096b652d397fac81515eb85d21a80172b5301bdb6b368186ea28d`.
- Validation result: read-only whole-directory PASS at `plan-ready`; implementation and Bootstrap Review remain unauthorized and unstarted.
- Affected slice: plan-local K2/K10 executable specification only; no K0 execution or production path change.
- Terminal revalidation: `validate_whole_directory.py --publish-plan-ready` passed idempotently after strengthening; state remained `plan-ready` and did not gain implementation authority.

## 2026-07-25: Knowledge maintenance and consumption repair

- Trigger: the maintainer added two requirements: a repository-local knowledge maintenance Skill and one standardized consumption path for CLI, Skill, Tool, MCP, document, and execution-plan consumers.
- Authority repair: the original-requirements file and Accepted ADR-0044 now define pinned local `refs/heads/main`, no implicit fetch, no dirty-worktree fact authority, closed-world `existing-only`, explicit `targeted`, provisional target-only worktree content, zero source mutation, and append-only maintenance evidence. ADR-0037 and ADR-0038 were not modified.
- Locator repair: K5 now specifies one deterministic core and CLI-first JSON adapter. Caller LLMs may provide semantic intent and hints only; adapter/Registry-owned authority, permission, Domain ceiling, snapshot and budget remain trusted fields. Results are source-location recommendations with mandatory hash revalidation, not generated fact answers.
- Maintenance repair: K14 now owns the future `.agents/skills/maintain-knowledge-base/SKILL.md` package as a thin adapter over deterministic snapshot, catalog, projection, validation and logging tools. Creating that Skill remains separately authorized implementation work.
- Materialized executable specification: four new closed-root request/result Schemas, 14 indexed knowledge-interface fixtures (five positive and nine negative), KC-041..KC-052, implementation-contract bindings, family-specific validator semantics, and two additional unit tests.
- Source identity: original-requirements SHA-256 `2aa794d6b7703e525b142e7c588496b651cdf8f336a5005c7a99fd931e5f600e`; ADR-0044 SHA-256 `f00a514bc41e1881f3a3f6a25226b9d757600b19412ab5233b9b6d819d2742fe`; Git HEAD and local `refs/heads/main` remained `7584f295c1b4d4124a4eaccc5ac51f05731ba923` during repair.
- Targeted validation: strict parsing passed for 61 JSON artifacts; `py -3 -B -m unittest discover -s tools/tests -p test_*.py` passed 10 tests, including exact positive/negative interface outcomes.
- Terminal validation: read-only whole-directory validation and `--publish-plan-ready` both passed. The K5 contract change required and received a K5-K14 plan-evidence replay; lifecycle remained `plan-ready` and `authorizes=["plan-ready"]`.
- Repository-level residual diagnostic: `py -3 scripts/python/validate_recovery_docs.py --dir execution-plans` remains nonzero because it applies the conventional recovery-plan header to standalone original-requirements files and several pre-existing legacy plans. This repair does not rewrite those unrelated plans; the scoped whole-directory validator and the repository 95-report index validator pass.
- Safety: no production Skill or Locator code, Phase production code, live metadata DB, live Hosted workspace, runtime, provider, Bootstrap Review, implementation authorization, or protected handoff was touched.

## 2026-07-26: Round 1 Bootstrap findings repaired

- Review evidence: `logs/ci/2026-07-25/kc-plan-r1e` was independently verified and finalized `blocked`; its validation envelope remains immutable and non-authorizing.
- Confirmed P1 repair: `jimuyun.hosted-context-manifest.v1` now rejects `enforcement_level=E2` unless `gate_mode=enforce`, with paired E1/observe and E2/observe fixtures.
- Confirmed P1 repair: Locator `matched` accepts only high or medium confidence; low confidence cannot pass the result Schema and the semantic guard also fails closed.
- Confirmed P1 repair: the trusted Locator envelope now requires a server-owned path-policy identity and repository-relative prefix boundaries; results bind that identity and every recommendation is checked with path-component containment.
- Confirmed P1 repair: maintenance results now require `before_snapshot_id` to equal the request `knowledge_snapshot_id` before closed-world or LKG semantics are evaluated.
- P2 repair: `00-index.md` now reports `plan-ready`, and the validator compares its single declared Status with `plan-state.v1.json`.
- Current executable specification: 15 closed-root Schemas, 20 indexed composition fixtures, 17 indexed knowledge-interface fixtures, one JCS/HMAC reference vector, and 15 plan-local tests.
- Targeted validation: strict parsing passed for 66 JSON artifacts; `py -3 -B -m unittest discover -s tools/tests -p test_*.py` passed 15 tests; read-only whole-directory validation passed with `implementation_authorized=false` and `bootstrap_review_started=true`.
- Lifecycle: `plan-ready` is preserved. Production implementation, K0 execution, protected-path writes, BH-HANDOFF, acceptance, release, archive, and Round 2 Bootstrap Review remain unauthorized.
- Safety: no Phase production code, live metadata DB, live Hosted workspace, runtime, provider, or protected shared LLM/Codex entrypoint was modified.

## 2026-07-26: K0 synthetic baseline completed

- Explicit maintainer authorization published `implementation-authorized` for K0-K10 plan-local work only.
- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K0/RUN-20260726T041004-923486Z`.
- RED observed `KC-K0-MISSING-MANIFEST`; GREEN and REFACTOR each validated a disposable synthetic root with no live paths, real accounts, provider secrets, metadata DB, or Hosted workspace access.
- The adapter router advanced to K1. This result authorizes no protected integration, acceptance, handoff, release, K11-K13 work, or K14 work.

## 2026-07-26: K1 ADR and authority contract completed

- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K1/RUN-20260726T041628-174364Z`.
- RED removed `Extends ADR-0037` in memory and observed `KC-K1-MISSING-ADR-RELATION`; GREEN and REFACTOR verified ADR-0044 relation text, ADR index presence, and implementation-contract binding.
- The adapter router may now advance to K2. This result does not alter ADR-0037/0038 or authorize protected integration.

## 2026-07-26: K2 schemas and fixtures completed

- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K2/RUN-20260726T041722-597403Z`.
- RED injected an unknown field into a valid plan-state instance and observed `schema_extra_property`; GREEN ran 15 plan-local validator tests; REFACTOR ran whole-directory composition validation.
- The adapter router may now advance to K3. No production schema consumer was changed.

## 2026-07-26: K3 snapshot foundation completed

- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K3/RUN-20260726T041823-207269Z`.
- RED rejected a protected Hosted-workspace path outside the allowed policy; GREEN generated a fresh temporary source snapshot; REFACTOR passed whole-directory validation.
- Inventory observation remained 9 Codex Hosted, 18 LLM Route Engine, 11 Python backend callers, with zero direct violations. The adapter router may now advance to K4.

## 2026-07-26: K4 repository catalog completed

- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K4/RUN-20260726T042916-955214Z`.
- RED enforced exclusion of `logs/phase-a-innernet/**`; GREEN regenerated a temporary source catalog and compared it byte-for-byte with the checked-in snapshot; REFACTOR preserved the deterministic inventory build.
- The adapter router may now advance to K5. No live runtime state was read or indexed.

## 2026-07-26: K5 Locator contract completed

- First bridge attempt failed after RED because a plan-local bridge call used an obsolete validator signature. No `slice-ready` result was emitted; the failed console evidence remains historical.
- Successful successor run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K5/RUN-20260726T043047-523396Z`.
- RED verified that a low-confidence `matched` result fails the Locator result Schema; GREEN executed the indexed knowledge-interface fixtures; REFACTOR passed whole-directory validation. The contract continues to bind ambiguity classification to `scripts/sc/_llm_backend.py::run_llm_exec` only.
- The adapter router may now advance to K6. No provider call was made.

## 2026-07-26: K6 experimental E1 projection completed

- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K6/RUN-20260726T043214-305035Z`.
- RED modeled E2 paired with `observe` and rejected it as non-releaseable; GREEN validated the E1/observe fixture; REFACTOR passed whole-directory composition validation.
- This is plan-local E1 evidence only. It did not change Hosted dispatch or authorize E2 integration. The adapter router may now advance to K7.

## 2026-07-26: K7 Template projection completed

- First bridge run failed during RED mutation self-check because the selected symbol also had call-site references. No `slice-ready` result was emitted.
- Successful successor run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K7/RUN-20260726T043342-914694Z`.
- RED removed the Seeder managed-path declaration in memory; GREEN confirmed the current Seeder source and source snapshot binding; REFACTOR passed whole-directory validation.
- The adapter router may now advance to K8. No Seeder behavior or workspace was modified.

## 2026-07-26: K8 synthetic Project Instance projection completed

- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K8/RUN-20260726T043452-571505Z`.
- RED rejected the cross-project-source fixture; GREEN ran the full composition fixture suite; REFACTOR passed whole-directory validation.
- This proves only synthetic isolation contracts. It does not deploy a Hosted project cache or alter a live workspace. The adapter router may now advance to K9.

## 2026-07-26: K9 synthetic Recovery projection completed

- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K9/RUN-20260726T043549-829705Z`.
- RED rejected the recovery-order mismatch fixture; GREEN ran composition fixtures; REFACTOR passed whole-directory validation.
- This is synthetic recovery-view evidence only. No live Hosted workspace, token, prompt, or host-path state was read. The adapter router may now advance to K10.

## 2026-07-26: K10 Context Assembler observe-only completed

- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K10/RUN-20260726T043649-540572Z`.
- RED rejected the modified signed-payload fixture; GREEN rebuilt the synthetic JCS/HMAC reference vector with payload SHA-256 `91d2a209fb0096b652d397fac81515eb85d21a80172b5301bdb6b368186ea28d`; REFACTOR passed whole-directory validation.
- K0-K10 are now complete as plan-local, synthetic, or observe-only evidence. No Phase production route, live metadata DB, live Hosted workspace, provider call, or shared protected LLM/Codex entrypoint was modified.
- K11-K13 remain blocked until BH-HANDOFF or formal merge/supersede decision and a new explicit user authorization. K14 remains separately authorized work after K13.

## 2026-07-26: Formal merge decision accepted and K0-K10 replayed

- Accepted ADR-0046 records the `formal_merge_decision`: it preserves the 2026-07-11 BH-HANDOFF boundary, permits only non-overlapping Knowledge Context K11-K13 work, and still requires separate explicit write authorization.
- Because ADR-0046 changed the implementation-contract hash, the earlier K0-K10 terminal results became stale. The adapter replayed K0-K9 under runs `RUN-20260726T044416-653163Z` through `RUN-20260726T044450-840753Z`, then replayed K10 under `RUN-20260726T044503-355689Z`.
- Current whole-directory validation passed after the replay. The adapter router now selects K11, but ADR-0046 does not itself authorize its write set.

## 2026-07-26: K11 caller inventory completed

- Adapter run: `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K11/RUN-20260726T044850-625956Z`.
- RED injected a synthetic direct invocation violation and observed `KC-K11-DIRECT-LLM-INVOCATION`; GREEN rebuilt all three inventories with 9 Codex Hosted callers, 18 LLM Route Engine callers, 11 Python backend callers, and zero direct violations; REFACTOR passed the whole-directory validator.
- The router may advance to K12. This remains read-only inventory evidence and does not authorize a protected shared-entrypoint write set.

## 2026-07-26: K11 reachability ledger repair and replay

- Added `hosted-callsite-migration-ledger.v1.json` and its deterministic builder. It derives Program endpoint bindings plus bounded static service-dependency closure from the frozen inventories.
- Current ledger closure contains 39 candidates: 26 `hosted-route`, 11 `toolchain`, one statically unreachable DI-only service, and one excluded Python backend definition; no reachability is `unknown`.
- The validator now requires exact ledger/inventory callsite closure, current source-snapshot binding, nonempty route evidence for Hosted entries, and a byte-for-byte rebuild. Unknown reachability fails closed before K12.
- This global contract and validator change invalidated previous hash-bound slice evidence. K0-K11 were replayed; the current K11 run is `logs/tdd-adapter/jimuyun-four-domain-knowledge-context.v1/K11/RUN-20260726T051610-052243Z`.

## 2026-07-26: K12 server-controlled gate migration completed

- Added the shared `HostedContextGate` seam to the C# LLM and Codex entrypoints under ADR-0044 and ADR-0046. Known LLM operations begin in `observe`; unlisted operations remain `legacy`; no caller can select a more permissive server mode.
- The gate returns only the stable K12 codes and records observe-only would-block telemetry. Targeted `LlmRouteEngineTests` and `CodexHostedProcessCommandFactoryTests` passed.
- No existing Hosted route was moved to `enforce`, no Browser/API surface changed, and no live workspace or metadata DB was read or modified.

## 2026-07-26: K13 persisted manifest and nonce validation milestone

- Added append-only manifest persistence and atomic nonce consumption to the metadata schema/store, plus a validator seam used only by an explicit `enforce` policy. Validation binds manifest, account, project, operation, snapshot, policy revision, signature, nonce, and expiry in one SQLite statement.
- Targeted storage and shared-entrypoint tests passed: 14 total. Replays, account/project mismatch, signature/snapshot/policy mismatch, and operation substitution are rejected without consuming a valid nonce.
- This is not E2 release readiness. No production route is `enforce`; JCS/HMAC key lifecycle, E2 predicate computation, route migration, Browser-safe error presentation, and live evidence remain incomplete. Live metadata and Hosted workspaces were not touched.

## 2026-07-26: K13 mechanical E2 readiness fail-closed check

- The plan validator now rejects an asserted `e2_readiness=true` unless the E2/enforce gate and the complete evidence set agree: manifest persistence, atomic nonce consumption, shared-entrypoint enforcement, every reachable callsite migration, inventory freshness, targeted test evidence, and rollback evidence. The incomplete-evidence negative fixture is covered by the terminal validator.
- Added `tools/check_e2_readiness.py`, which reads the generated migration ledger and direct-invocation inventory instead of accepting a hand-declared readiness value. Its current result is `ready=false`: 26 reachable Hosted callsites are not enforced, while direct violations and unknown reachability are both zero.
- The same check requires a current snapshot-bound `e2-release-evidence.v1.json`, which intentionally does not exist until signature lifecycle, caller migration, rollback evidence, and targeted validation are complete. This preserves a fail-closed path and does not authorize release or E2.

## 2026-07-26: K13 HMAC key-id validation milestone

- Added a versioned canonical manifest-record payload, HMAC-SHA-256 verification, key-id binding, fixed-time signature comparison, and retained-key verification for rotation. The signed record binds account, project, operation, snapshot, policy revision, nonce, creation, expiry, and key id.
- Database persistence now records `key_id`; the compatibility migration adds it with an empty default so historical unsigned rows cannot pass the new verifier. The atomic consume query also binds creation and expiry values supplied by the signed envelope.
- Targeted shared-entrypoint, storage, and signing tests passed: 15 total. This verifier is intentionally not registered with any production route yet: a distinct host-secret source, server-owned manifest issuer, and caller migration are still required. No runtime configuration, live DB, or Hosted workspace changed.

## 2026-07-26: K13 server-owned manifest issuer milestone

- Added an issuer that alone generates the manifest ID, nonce, bounded fifteen-minute lifetime, canonical signed record, and persisted envelope. A caller receives only the completed envelope after durable save; it cannot select a key id, nonce, or signature.
- The issuer/validator round trip validates signature, account/project/operation binding, expiry, and single-use nonce consumption. The out-of-range lifetime path is rejected. Shared-entrypoint and manifest tests passed: 17 total.
- The issuer remains unregistered. Reaching a real enforce path now requires a separately authorized change to `Program.cs` and the protected `runtime/phase-a/start-phasea.ps1` to provision a distinct host secret, followed by explicit per-caller migration. This work did not alter either protected path, live state, or Browser/API behavior.

## 2026-07-26: K13 distinct key-ring configuration milestone

- Added fail-closed parsing for `PHASEA_HOSTED_CONTEXT_SIGNING_ACTIVE_KEY_ID` and `PHASEA_HOSTED_CONTEXT_SIGNING_KEYS_JSON`. The ring requires an active key present in a non-empty, duplicate-free JSON key list; it retains verification keys for rotation.
- The parser neither reads nor falls back to ticket or web-preview signing secrets. Missing, partial, malformed, duplicate, and empty-secret configurations fail without persisting key material. Configuration tests passed: 32 total.
- The key ring is not yet registered with the issuer or runtime startup. Doing so remains inside the prepared K13 protected write set and requires authorization for `Program.cs` and `runtime/phase-a/start-phasea.ps1`.

## 2026-07-26: K13 concurrent nonce and expiry evidence

- Added concurrent consume coverage against the temporary SQLite metadata store: sixteen validators race on one signed envelope and exactly one may consume its nonce.
- Added an expiry case proving that a valid HMAC does not bypass the persisted expiry condition. Manifest issuer tests passed: 4 total.
- These tests use a temporary database only. They do not register runtime services, alter protected startup behavior, or modify live metadata/workspaces.

## 2026-07-26: K13 protected runtime key-ring integration

- Under explicit protected-path authorization, `Program.cs` conditionally registers the signer, server-owned issuer, and validator only when the complete dedicated key ring is configured. Without it, existing legacy/observe behavior remains compatible and any future enforce request fails closed.
- `runtime/phase-a/start-phasea.ps1` resolves the paired dedicated key-ring values from host environment sources, rejects a half-configured pair, and passes both values to the child process. It does not generate a replacement key or use ticket/web-preview secrets as fallback.
- PowerShell parser validation, platform build, and 52 targeted configuration/manifest/shared-entrypoint tests passed. The live service was not started or restarted, so no live metadata, workspace, runtime state, or public behavior changed.

## 2026-07-26: K13 read-only enforce pilot

- Migrated the JSON-only `llm:gdd-question-form` dispatch behind `/api/projects/{projectId}/gdd/question-form` from the server's default observe policy to `enforce` only when the dedicated Hosted Context key ring is configured. All other known operations retain observe and unregistered operations retain legacy behavior.
- `GameDesignQuestionFormService` now obtains a five-minute server-issued envelope before dispatch. The request binds the server account, project, `llm:gdd-question-form` operation, deterministic project snapshot, policy revision, signature key id, signature, nonce, and expiry. Issuance failure returns the existing browser-safe fallback with `context_manifest_issue_failed` without dispatching the LLM.
- Added service and gate-policy tests. The selected configuration, signing, manifest, question-form, LLM route, and Codex factory suite passed 69 tests. Existing unrelated nullable warnings remain in the test project.
- Updated the deterministic migration-ledger builder and its Schema/whole-directory guard to recognize only source-derived `legacy/pending` or `enforce/enforced` Hosted-route pairs. Inventory snapshot `7ef32d02d1d55c683104bd883cf275a86e07daea547b5cf0e70a79b247b1e84c` records 26 reachable Hosted callsites, one enforced pilot, 25 not enforced, zero unknown reachability, and zero direct-invocation violations.
- `tools/check_e2_readiness.py` remains fail-closed with `ready=false`, blocked by the remaining reachable callsites and the intentionally absent `e2-release-evidence.v1.json`. No E2 release claim, live-service restart, live metadata change, or Hosted-workspace access occurred.

## 2026-07-26: K13 question-form cache-decision enforce completion

- The same read-only question-form endpoint has a second LLM dispatch, `llm:gdd-question-form-cache-decision`, which determines whether an already agent-generated form remains reusable. It now receives a separate five-minute server-issued envelope and is `enforce` when the dedicated key ring is configured.
- Issuer failure is conservative: the service reuses the cached form and does not dispatch the LLM. This retains the endpoint's existing cache-safe behavior while eliminating a gate bypass.
- Targeted question-form and LLM-gate tests passed 26/26. Inventory snapshot `5ee9c0aa02f46ffb65de42f14162e6daf07d629897d2adec0351b083c2de0544` records two enforced Hosted callsites, 24 remaining not enforced, zero unknown reachability, and zero direct-invocation violations. E2 remains not ready and no live service was restarted.

## 2026-07-26: K13 read-only routing and scene-draft batch

- `llm:project-workflow-route-intent` now binds a server-issued envelope before classifying a user message. Manifest issuance failure returns the pre-existing browser-safe `general_chat` no-route result with `context_manifest_issue_failed`; it does not dispatch the LLM.
- `llm:gdd-scene-route-draft` now binds a server-issued envelope before generating an unconfirmed scene draft. Manifest issuance failure uses its existing scene-route fallback without dispatching the LLM.
- Targeted workflow-route/LLM tests passed 29/29 and scene-route/LLM tests passed 18/18. Inventory snapshot `7d61cb0aca5dbe4c21ce510f11d109c15aa5e5faf59212e8367ea71a4d012b89` records four enforced Hosted callsites and 22 remaining not enforced. No live service, metadata DB, or Hosted workspace was accessed.
- Remaining LLM callers that are reachable either generate persisted route artifacts, create runs, seed a workspace, or invoke executable Codex workflows. The next migration must therefore supply a frozen mutation-capable write set with explicit fallback and rollback evidence before it is enforced.

## 2026-07-26: K13 requirement-map enforce migration

- Added `12-k13-requirement-map-write-set.md` before migrating `llm:gdd-requirement-map`. Its snapshot binds the current GDD content hash, confirmed scene-route hash, project/account identity, and deterministic requirement floor.
- The LLM is called only after the server has issued the envelope. Issuance failure returns the existing deterministic `needs_review` requirements fallback with `context_manifest_issue_failed`; the route may then persist its established recovery artifacts and database binding, but cannot dispatch an unbound LLM call.
- The focused envelope assertion is included in the existing structured requirements and capability-evidence test. The combined configuration, manifest, question-form, scene-route, workflow-route, requirement-map, shared LLM, and Codex-factory suite passed 196/196.
- Inventory snapshot `7604712ca1a03a49b3255bc7d834d5ecca2d1c0fa245297a40393caf698d35d8` records five enforced Hosted callsites, 21 remaining not enforced, zero unknown reachability, and zero direct-invocation violations. E2 is still false because all reachable callsites and final release evidence are required.

## 2026-07-26: K13 draft-import guarded migration

- `llm:draft-analysis`, `llm:draft-coverage`, and `llm:draft-coverage-retry` now obtain distinct server-issued envelopes before dispatch. A signing failure disables the affected LLM request and retains the existing deterministic draft or coverage fallback.
- The E2 configuration path disables the legacy direct `IAiCodeMirrorResponsesClient` coverage call, so a configured Hosted Context gate cannot be bypassed by that alternate provider transport. Legacy behavior remains unchanged when no dedicated key ring is configured.
- Focused envelope coverage plus existing draft-import regression tests passed 22/22. The new test captures all three operation keys and proves each carries an account/project/operation-bound envelope with the server key id. The updated source-generated ledger records eight enforced callsites, 18 pending reachable callsites, no direct-invocation violations, and no unknown reachability.

## 2026-07-26: K13 iteration-plan LLM enforce migration

- `PrototypeIterationPlanService` now creates a fresh server-issued envelope for each model-backed operation: `llm:planning-analysis`, `llm:goal-plan`, `llm:prototype-skeleton-regeneration-guard`, and `llm:plan-evaluation`. The four operations are explicit `enforce` overrides in the shared Hosted Context gate.
- A signing or persistence failure cannot dispatch an unbound request. Mandatory goal planning fails with a route error; planning analysis retains its pre-existing deterministic fallback where allowed; the skeleton guard returns its conservative no-recreation decision; evaluation returns its established failed-evaluation result.
- The focused test captures the model-backed goal-plan request and verifies account, project, operation, and active signing-key binding. `PrototypeIterationPlanServiceTests` passed 68/68. Inventory snapshot `41f4a77f621d23e76014f0b9e1c02eeca2daad20689e848e39362a7c08534095` records 15 enforced and 11 pending reachable Hosted callsites, with zero unknown reachability and zero direct invocation violations. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K13 GDD next-step review enforce migration

- `GddMilestoneStepService` now issues `llm:gdd-next-step-review` before asking the model to revise the next unlocked milestone. The operation is an explicit shared-gate `enforce` override.
- Manifest issuance failure preserves the existing conservative behavior: the next GDD step remains unchanged and no LLM dispatch occurs. A valid request binds the account, project, operation, prompt-derived snapshot, policy revision, and current signing-key id.
- The existing adjustment test now verifies the issued envelope. `GddMilestoneStepServiceTests` passed 39/39. Inventory snapshot `55cb0be6a28147ca6b4288cd0b80fcf43f34782d21640fc1baf751b517e30622` records 16 enforced and 10 pending reachable Hosted callsites, with zero unknown reachability and zero direct invocation violations. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K13 executable iteration-goal Codex enforce migration

- `CodexHostedProcessCommandFactory.BuildAsync` now performs the same server-policy structural gate as `Build`, then validates and atomically consumes the signed manifest before returning a command for dispatch. An enforce-mode request with a missing validator, invalid envelope, stale signature, or consumed nonce fails with `context_manifest_invalid` before a process is run.
- `PrototypeIterationGoalService` now signs `codex:prototype-iteration-goal` with account, project, run, operation, and prompt-derived snapshot binding, and sends it through `BuildAsync` before its `workspace-write` Codex command is given runtime credentials or passed to the process runner. A failed issuance or validation follows the service's existing run-failure path and cannot dispatch Codex.
- The inventory scanner now recognizes both `Build` and `BuildAsync`, preventing a safe shared-entrypoint upgrade from accidentally removing a callsite from the migration ledger. The ledger builder now evaluates Codex Hosted operation keys as well as LLM Route Engine operation keys.
- The combined `CodexHostedProcessCommandFactoryTests`, `PrototypeIterationGoalServiceTests`, and `LlmRouteEngineTests` suite passed 71/71. Inventory snapshot `2d6b8f1827a7507ea47280168b77b2ef4a303e9ac6208500ed98847dabd7cf27` records 17 enforced and 9 pending reachable Hosted callsites, with zero unknown reachability and zero direct invocation violations. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K13 executable quick-fix Codex enforce migration

- `PrototypeQuickFixService` now signs and validates `codex:prototype-quick-fix` before passing its focused `workspace-write` command to the runtime credential and process runner. The prompt-derived snapshot also binds account, project, and run identity.
- Issuer or validator failure is handled by the pre-existing quick-fix exception path: the run is completed as failed with additive evidence and no Codex process is dispatched.
- The existing quick-fix execution test verifies the manifest account/project/operation/key binding and the shared factory validator captures the consumption operation. The combined factory, iteration-goal, and quick-fix suite passed 158/158. Inventory snapshot `9ce829e51360709e5e127e9dc25055f52d1de811eeda59daaee4e865f6da8b6a` records 18 enforced and 8 pending reachable Hosted callsites, with zero unknown reachability and zero direct invocation violations. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K13 post-validation workflow repair Codex enforce migration

- The inventory-visible direct Codex path in `PrototypeWorkflowService` is the post-validation repair command, distinct from the service's Python workflow creation and ordinary-repair commands. It now issues and validates `codex:prototype-post-validation-repair` before runtime credentials or the process runner receive the workspace-write command.
- The operation binds account, project, run, prompt-derived snapshot, policy revision, signature key, and nonce. Its existing queued repair exception path retains failure evidence and no process can start after issuer or validator failure.
- `PrototypeWorkflowTests` passed 64/64, including a focused post-validation repair assertion for the envelope binding. Inventory snapshot `d0869d434a89702233bfa28d2389249bf9bd61f8263e7e918840d5cba2af5df5` records 19 enforced and 7 pending reachable Hosted callsites, with zero unknown reachability and zero direct invocation violations. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K13 asset-inventory and UI-optimization enforce migration

- `ProjectAssetInventoryService` now issues `llm:asset-inventory-judgement` before its read-only judgement request. Issuance failure completes the run with `context_manifest_issue_failed` and returns the deterministic candidates without model dispatch. Its focused readback suite passed 69/69.
- `PrototypeUiOptimizationService` now uses `BuildAsync` for `codex:prototype-ui-optimization`, binding account, project, run, prompt-derived snapshot, policy revision, key id, and nonce before its workspace-write command runs. Its existing failure evidence path handles issuer or validator failure. Its focused suite passed 28/28.
- Inventory snapshot `27d63ee2f6874ef96b86c51a63862baa843bd56ad054781ac4f0f68685f81000` records 21 enforced and 5 pending reachable Hosted callsites, with zero unknown reachability and zero direct invocation violations. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K13 remaining Hosted caller migrations

- `GameDesignDocumentService` now mints a fresh `codex:gdd-document-generation` envelope for every capacity-retry attempt before `BuildAsync` can return a process command. The bound snapshot contains the account, project, run, operation, and prompt; an earlier consumed nonce can therefore never authorize a retry.
- The dedicated and semantic web-preview adapters now use `BuildAsync` with `codex:web-preview-dedicated-adapter` and `codex:web-preview-semantic-adapter`. Semantic reuse decisions and adapter generation share the latter operation because they are one adapter contract and must pass the same server-side envelope validation before a process dispatches.
- `SkillActionService` now selects `codex:skill-action` for executable workspace-write actions and `llm:skill-action` for read-only LLM actions. Both issue account/project/run/action/prompt-bound envelopes; issuance failure produces `context_manifest_issue_failed` without LLM or Codex dispatch.
- Inventory snapshot `03c54fc67253d67a4a9264c3c4bf795cc78e0a67e1cf60c8f0bb999ce1061410` records all 25 reachable Hosted callsites as enforced, 13 non-reachable Python toolchain entries excluded, zero unknown reachability, and zero direct invocation violations. The current mechanical readiness result remains fail-closed solely because release evidence is intentionally absent.
- `ProjectWebPreviewSemanticAdapterServiceTests`, `SkillActionServiceTests`, and the representative `GameDesignDocumentServiceTests.CreateAsync_ShouldWriteGddWithBmadContextAndArtifact` passed 12/12. `PhaseA.Platform` builds without warnings or errors. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K13 release-validation boundary

- The current signed-manifest lifecycle, persistence, signature rotation/tamper, expiry, atomic nonce-consumption, shared LLM gate, and shared Codex-factory checks passed 21/21. Together with the remaining-caller regression set, the current focused evidence is 33/33.
- `dotnet test PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj --no-restore` did not finish before a ten-minute command limit. A five-minute `--blame-hang --blame-hang-timeout 2m` replay also did not finish and did not emit a single-test hang diagnosis. Neither command is counted as a pass.
- Consequently, `e2-release-evidence.v1.json` remains absent and `tools/check_e2_readiness.py` remains fail-closed. This is a validation gap, not an E2 declaration; no live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K13 complete platform-test partitions

- The 1447 listed `PhaseA.Platform.Tests` cases completed through two overlapping namespace partitions, avoiding the terminal's ten-minute whole-command limit: the non-`Runs` partition passed 767/767 in 6m23s and the `Runs` partition passed 846/846 in 8m33s. Every listed test is in the union of those partitions; the overlap does not reduce coverage.
- This closes the prior full-suite execution gap, but does not authorize E2 release. ADR-0046 expressly excludes production release authorization, and its gate remains controlling even after local tests, inventories, and validators are current.
- `e2-release-evidence.v1.json` remains absent. A future release decision must bind the current source snapshot, signature lifecycle, current rollback evidence, and this validation record before `tools/check_e2_readiness.py` may report `ready=true`.

## 2026-07-26: K13 readiness declaration and K14 maintenance start

- Accepted ADR-0047 authorizes only a repository and plan-local E2 readiness declaration. It deliberately excludes service restart, runtime configuration, public deployment, live metadata, and Hosted-workspace mutation. The current evidence is bound to the source snapshot and `tools/check_e2_readiness.py` reports `ready=true`.
- K14 now includes `.agents/skills/maintain-knowledge-base`: a concise Skill contract and a deterministic Python runner. The runner pins `refs/heads/main`, rejects fetch/dirty-authority/source-write requests, refreshes existing catalog entries in closed-world mode, confines targeted discovery, and writes only derived output plus append-only evidence under `logs/knowledge-context`.
- Skill structure validation and Python compilation passed. A malformed fixture-envelope invocation was rejected as `invalid_request`, preserving the fail-closed input boundary. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K14 maintenance contract execution coverage

- The isolated maintenance-runner test now proves main-backed existing-only refresh, strict closed-world behavior for unregistered main files, incremental unchanged replay with LKG preservation, local-main commit mismatch rejection, and worktree-only targeted content recorded only as a provisional candidate.
- The runner accepts the legacy `source-snapshot.v1` `files` shape as a read-only catalog compatibility input and normalizes it without source mutation. Its result `log_ref` now names the exact timestamped append-only result sidecar that was written.
- `MAINTAIN_KNOWLEDGE_TEST PASS`, Skill validation, and whole-directory validation pass. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K14 initial other-domain catalogs

- Added initial plan-local derived catalogs for `toolchain`, shared-repository `workspace`, and `marketplace`. Each catalog pins `refs/heads/main` and records source paths and hashes only. Marketplace is explicitly empty with `empty-no-external-discovery`; no external source was invented or fetched.
- A real existing-only Toolchain refresh completed against main commit `7584f295c1b4d4124a4eaccc5ac51f05731ba923`. Both registered entries were unchanged, LKG was preserved, source mutation count was zero, and the timestamped append-only result sidecar is referenced from `projections/toolchain.maintenance-result.v1.json`.
- Whole-directory validation and the isolated maintenance-runner contract suite pass. No live service, metadata DB, or Hosted workspace was accessed.

## 2026-07-26: K14 completion evidence

- The maintenance-runner regression now confirms retention: two refreshes preserve multiple timestamped append-only sidecars. Combined with the prior closed-world, main pin, provisional, source-boundary, incremental/LKG, and legacy-index cases, this completes the K14 maintenance contract.
- `check_e2_readiness.py` reports `ready=true`; `MAINTAIN_KNOWLEDGE_TEST PASS`, Skill validation, whole-directory validation, and `git diff --check` pass. All K0-K14 slices now have current local implementation evidence. This report records no operational deployment, live metadata mutation, or Hosted-workspace access.

## Implementation completion

- Observed at: `2026-07-26T11:15:12.081843+00:00`
- Publisher: `tools/publish_implementation_complete.py` through the Quick Dev adapter bridge.
- Result: `implementation-complete`; this does not authorize acceptance, deployment, handoff, release, or archive.

## Implementation repair completion

- Observed at: `2026-07-31T11:52:45.594533+00:00`
- Publisher: `tools/publish_implementation_complete.py` through the Quick Dev adapter bridge.
- Repair binding: `sha256:6d69bc586d341579697ebea2364482458eea50cacf88621401e5f41e80206ed7`
- Result: `implementation-complete`; this does not authorize acceptance, deployment, handoff, release, or archive.
