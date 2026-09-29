# TC-D1 Atomic Obligation Register

Each row is one independent acceptance unit. Commands and runtime receipts are pending Architecture/implementation binding; no execution is claimed.

| ID | Exact source | Trigger | Observable behavior | Success / rejection | Independent witness | Acceptance / capability |
| --- | --- | --- | --- | --- | --- | --- |
| AO-01a | FR-1 missing target | absent path | reject invalid-input | absent-path fixture | isolated absent-path-fixture fixture; hold all other inputs constant | A03/CAP-1/pending independent witness |
| AO-01b | FR-1 non-directory | file path | reject invalid-input | file-target fixture | isolated file-target-fixture fixture; hold all other inputs constant | A03/CAP-1/pending independent witness |
| AO-01c | FR-1 escaping | traversal path | reject invalid-input | traversal fixture | isolated traversal-fixture fixture; hold all other inputs constant | A03/CAP-1/pending independent witness |
| AO-02a | FR-1 unsupported | unsupported package | reject/no result | unsupported fixture | isolated unsupported-fixture fixture; hold all other inputs constant | A03/CAP-1/pending independent witness |
| AO-02b | FR-1 minimum set | remove VDD/Acceptance | reject policy reduction | policy-removal fixture | isolated policy-removal-fixture fixture; hold all other inputs constant | A04/CAP-1/pending independent witness |
| AO-03a | FR-2 effective target | adapter reads other target | identity-invalid | instrumented adapter | isolated instrumented-adapter fixture; hold all other inputs constant | A06-A07/CAP-1/pending independent witness |
| AO-04a | FR-3 missing validator | validator absent | identity-invalid | missing-validator fixture | isolated missing-validator-fixture fixture; hold all other inputs constant | A05-A07/CAP-2/pending independent witness |
| AO-04b | FR-3 substituted validator | undeclared validator | identity-invalid | substitution fixture | isolated substitution-fixture fixture; hold all other inputs constant | A05-A07/CAP-2/pending independent witness |
| AO-04c | FR-3 escaping validator | root escape | identity-invalid | escape fixture | isolated escape-fixture fixture; hold all other inputs constant | A05-A07/CAP-2/pending independent witness |
| AO-05a | FR-3 validator drift | content changes | stale | byte mutation | isolated byte-mutation fixture; hold all other inputs constant | A06-A07/CAP-2/pending independent witness |
| AO-05b | FR-3 dependency drift | dependency changes | stale | dependency mutation | isolated dependency-mutation fixture; hold all other inputs constant | A06-A07/CAP-2/pending independent witness |
| AO-05c | FR-3 incompatibility | contract mismatch | identity-invalid | incompatible fixture | isolated incompatible-fixture fixture; hold all other inputs constant | A06-A07/CAP-2/pending independent witness |
| AO-06a | FR-3 self-selection | candidate selects identity | reject trust | candidate descriptor | isolated candidate-descriptor fixture; hold all other inputs constant | A05-A07/CAP-2/pending independent witness |
| AO-06b | FR-3 forged version | version text only | reject trust | forged output | isolated forged-output fixture; hold all other inputs constant | A05-A07/CAP-2/pending independent witness |
| AO-06c | FR-3 always-success | all inputs pass | no Replay Result | always-pass validator | isolated always-pass-validator fixture; hold all other inputs constant | A07/CAP-2/pending independent witness |
| AO-07a | FR-4 positive Probe | valid detached input | pass with bindings | independent valid fixture | isolated independent-valid-fixture fixture; hold all other inputs constant | A06-A07/CAP-2/pending independent witness |
| AO-08a | FR-4 negative Probe | declared defect input | fail expected category | malformed fixture; infra controls separate | isolated malformed-fixture;-infra-controls-separate fixture; hold all other inputs constant | A06-A07/CAP-2/pending independent witness |
| AO-09a | FR-5 historical bytes | frozen file write | reject mutation | blob comparison | isolated blob-comparison fixture; hold all other inputs constant | A01-A02/CAP-3/pending independent witness |
| AO-09b | FR-5 historical validator | reference inspected | identity auditable | validator blob | isolated validator-blob fixture; hold all other inputs constant | A08/CAP-3/pending independent witness |
| AO-09c | FR-5 original command | command evidence altered | reject alteration | command mutation | isolated command-mutation fixture; hold all other inputs constant | A08/CAP-3/pending independent witness |
| AO-09d | FR-5 wrapper replay | wrapper not launched | reject no-launch | no-launch fixture | isolated no-launch-fixture fixture; hold all other inputs constant | A08/CAP-3/pending independent witness |
| AO-09e | FR-5 replay binding | identity mismatch | reject replay | binding mutation | isolated binding-mutation fixture; hold all other inputs constant | A08/CAP-3/pending independent witness |
| AO-09f | FR-5 authority limit | history promoted | reject promotion | forged handoff | isolated forged-handoff fixture; hold all other inputs constant | A08/CAP-3/pending independent witness |
| AO-10a | FR-6 seed uniqueness | missing/duplicate seed | reject | cardinality fixture | isolated cardinality-fixture fixture; hold all other inputs constant | A09/CAP-3/pending independent witness |
| AO-10b | FR-6 seed provenance | provenance absent | reject | provenance deletion | isolated provenance-deletion fixture; hold all other inputs constant | A09/CAP-3/pending independent witness |
| AO-10c | FR-6 seed missing | evidence absent | reject | missing evidence | isolated missing-evidence fixture; hold all other inputs constant | A10/CAP-3/pending independent witness |
| AO-10d | FR-6 seed drift | content changes | stale | seed mutation | isolated seed-mutation fixture; hold all other inputs constant | A10/CAP-3/pending independent witness |
| AO-10e | FR-6 classification | disallowed class | reject promotion | classification fixture | isolated classification-fixture fixture; hold all other inputs constant | A11/CAP-3/pending independent witness |
| AO-10f | FR-6 baseline output | baseline label | reject | baseline-label fixture | isolated baseline-label-fixture fixture; hold all other inputs constant | A11/CAP-3/pending independent witness |
| AO-11a | FR-7 Stable provenance | source absent | Stable ineligible | unproven source | isolated unproven-source fixture; hold all other inputs constant | A12/CAP-4/pending independent witness |
| AO-11b | FR-7 Stable immutable | identity changes | stale | identity mutation | isolated identity-mutation fixture; hold all other inputs constant | A12/CAP-4/pending independent witness |
| AO-12a | FR-8 valid case | one side missing | aggregate reject | missing-side fixture | isolated missing-side-fixture fixture; hold all other inputs constant | A12/CAP-4/pending independent witness |
| AO-12b | FR-8 invalid case | copied output | aggregate reject | copy fixture | isolated copy-fixture fixture; hold all other inputs constant | A12/CAP-4/pending independent witness |
| AO-12c | FR-8 historical case | relabelled case | aggregate reject | relabel fixture | isolated relabel-fixture fixture; hold all other inputs constant | A12/CAP-4/pending independent witness |
| AO-13a | FR-9 workflow consumer | route unreachable | closure reject | unreachable fixture | isolated unreachable-fixture fixture; hold all other inputs constant | A13/CAP-5/pending independent witness |
| AO-13b | FR-9 VDD consumer | omitted caller | closure reject | omission fixture | isolated omission-fixture fixture; hold all other inputs constant | A13/CAP-5/pending independent witness |
| AO-13c | FR-9 Acceptance consumer | omitted caller | closure reject | omission fixture | isolated omission-fixture fixture; hold all other inputs constant | A13/CAP-5/pending independent witness |
| AO-14a | FR-10 enable | approved candidate | real Candidate call | no-call fixture | isolated no-call-fixture fixture; hold all other inputs constant | A15/CAP-5/pending independent witness |
| AO-14b | FR-10 disable | candidate enabled | real Prior call | config-only fixture | isolated config-only-fixture fixture; hold all other inputs constant | A15/CAP-5/pending independent witness |
| AO-14c | FR-10 rollback | rollback applicable | Prior identity/verdict/category restored | rejection-only fixture | isolated rejection-only-fixture fixture; hold all other inputs constant | A15/CAP-5/pending independent witness |
| AO-14d | FR-10 re-enable | candidate current | real Candidate call | skip fixture | isolated skip-fixture fixture; hold all other inputs constant | A15/CAP-5/pending independent witness |
| AO-15a | FR-11 Exact Cover | coverage built | no orphan nodes | orphan mapping fixture | isolated orphan-mapping-fixture fixture; hold all other inputs constant | A01-A17/CAP-6/pending independent witness |
| AO-16a | FR-12 snapshot | bound input changes | reproduce or stale | reconstruction mutation | isolated reconstruction-mutation fixture; hold all other inputs constant | A06/A08/CAP-7/pending independent witness |
| AO-17a | FR-13 authorization | non-empty auth | reject publication | forged auth | isolated forged-auth fixture; hold all other inputs constant | A14/CAP-8/pending independent witness |
| AO-17b | FR-13 lifecycle | foreign state | reject publication | foreign-state fixture | isolated foreign-state-fixture fixture; hold all other inputs constant | A14/CAP-8/pending independent witness |
| AO-18a | NFR-1 fail closed | unknown fact | unsuccessful terminal | corrupt fact | isolated corrupt-fact fixture; hold all other inputs constant | NFR-1/CAP-6/pending independent witness |
| AO-18b | NFR-2 auditability | missing trace | evidence-invalid | binding deletion | isolated binding-deletion fixture; hold all other inputs constant | NFR-2/CAP-6/pending independent witness |
| AO-18c | NFR-3 reproducibility | fresh mismatch | fail closed | fresh checkout | isolated fresh-checkout fixture; hold all other inputs constant | NFR-3/CAP-7/pending independent witness |
| AO-18d | NFR-4 isolation | shared mutable evidence | reject | cross-case substitution | isolated cross-case-substitution fixture; hold all other inputs constant | NFR-4/CAP-4/pending independent witness |
| AO-18e | NFR-5 immutability | historical mutation | reject write | rename/delete attempt | isolated rename/delete-attempt fixture; hold all other inputs constant | NFR-5/CAP-3/pending independent witness |
| AO-18f | NFR-6 platform | profile authority/path mismatch | reject | Windows/profile fixture | isolated Windows/profile-fixture fixture; hold all other inputs constant | NFR-6/CAP-1/pending independent witness |
| AO-18g | NFR-7 bounded | timeout/output limit | unsuccessful; coverage unchanged | timeout fixture | isolated timeout-fixture fixture; hold all other inputs constant | NFR-7/CAP-4/pending independent witness |
| AO-18h | Guardrail installed paths | write protected BMAD/GDS | reject write | protected-path fixture | isolated protected-path-fixture fixture; hold all other inputs constant | A16/CAP-8/pending independent witness |
| AO-18l | A16 Phase boundary | Phase file write | reject write | Phase fixture | isolated Phase-fixture fixture; hold all other inputs constant | A16/CAP-8/pending independent witness |
| AO-18m | A16 runtime boundary | runtime file write | reject write | runtime fixture | isolated runtime-fixture fixture; hold all other inputs constant | A16/CAP-8/pending independent witness |
| AO-18n | A16 Hosted workspace | workspace write | reject write | workspace fixture | isolated workspace-fixture fixture; hold all other inputs constant | A16/CAP-8/pending independent witness |
| AO-18o | A16 account boundary | account write | reject write | account fixture | isolated account-fixture fixture; hold all other inputs constant | A16/CAP-8/pending independent witness |
| AO-18p | A16 sandbox boundary | sandbox write | reject write | sandbox fixture | isolated sandbox-fixture fixture; hold all other inputs constant | A16/CAP-8/pending independent witness |
| AO-18q | A17 roadmap separation | TC-E0/D2-D6 work | reject scope | roadmap fixture | isolated roadmap-fixture fixture; hold all other inputs constant | A17/CAP-8/pending independent witness |
| AO-18r | A17 no promotion | promotion requested | reject | promotion fixture | isolated promotion-fixture fixture; hold all other inputs constant | A17/CAP-8/pending independent witness |
| AO-18s | A17 no Miner/Curator | feature requested | reject | feature fixture | isolated feature-fixture fixture; hold all other inputs constant | A17/CAP-8/pending independent witness |
| AO-18t | A17 no autonomous/ranking/RL | autonomy requested | reject | autonomy fixture | isolated autonomy-fixture fixture; hold all other inputs constant | A17/CAP-8/pending independent witness |
| AO-03b | FR-3 successful receipt provenance | validator executes successfully | receipt records trusted content identity and descriptive validator version | remove version/content fields | isolated remove-version/content-fields fixture; hold all other inputs constant | A06/CAP-2/pending independent witness |
| AO-10g | FR-6 seed applicability | seed applicability omitted or false | seed record rejected | applicability deletion fixture | isolated applicability-deletion-fixture fixture; hold all other inputs constant | A09/CAP-3/pending independent witness |
| AO-10h | FR-6 seed missing label | missing label omitted | seed record rejected | missing-label fixture | isolated missing-label-fixture fixture; hold all other inputs constant | A10/CAP-3/pending independent witness |
| AO-10i | FR-6 seed counterexample | counterexample/explicit absence omitted | seed record rejected | counterexample deletion fixture | isolated counterexample-deletion-fixture fixture; hold all other inputs constant | A10/CAP-3/pending independent witness |
| AO-18u | New PRD guardrail no replacement tree | alternate TC-D1 directory created | scope rejected | directory-injection fixture | isolated directory-injection-fixture fixture; hold all other inputs constant | guardrail/CAP-8/pending independent witness |
| AO-18v | New PRD guardrail Skill-input v2 | v1/current-pointer redesign proposed | scope rejected | protocol-redesign fixture | isolated protocol-redesign-fixture fixture; hold all other inputs constant | guardrail/CAP-8/pending independent witness |
| AO-18w | New PRD guardrail defect-revealing tests | production change lacks prior real RED test | change rejected | missing-RED fixture | isolated missing-RED-fixture fixture; hold all other inputs constant | guardrail/CAP-6/pending independent witness |
| AO-12d1 | FR-8 dirty baseline | undeclared baseline change | contamination rejected | dirty-baseline fixture | A12 | CAP-4/A12 |
| AO-12d2 | FR-8 knowledge collision | read-set self-collision | collision rejected | collision fixture | A12 | CAP-4/A12 |
| AO-12d3 | FR-8 policy/index gap | required relation absent | fail closed | policy-gap fixture | A12 | CAP-4/A12 |

## Bidirectional mapping
Every effective FR consequence, NFR, guardrail, and retained A01-A17 duty maps to dedicated rows above, and every row names its exact source and acceptance/capability. Mapping is many-to-many only where the witness independently observes each duty. Historical mapping: A01→AO-09a; A02→AO-09a; A03→AO-01a/b/c,AO-02a,AO-03a; A04→AO-02b; A05→AO-04a/b/c,AO-06a/b; A06→AO-03a,AO-03b,AO-05a/b/c,AO-07a,AO-08a; A07→AO-01a through AO-08a; A08→AO-09b/c/d/e/f; A09→AO-10a/b,AO-10g; A10→AO-10c/d,AO-10h/i; A11→AO-10e/f; A12→AO-11a/b,AO-12a/b/c,AO-12d1/d2/d3; A13→AO-13a/b/c; A14→AO-17a/b; A15→AO-14a/b/c/d; A16→AO-18h,AO-18l,AO-18m,AO-18n,AO-18o,AO-18p; A17→AO-18q–t. Guardrails map to AO-18u/v/w.
