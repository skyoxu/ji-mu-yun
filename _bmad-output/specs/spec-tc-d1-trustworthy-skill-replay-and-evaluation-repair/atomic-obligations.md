# TC-D1 Atomic Obligation Register

Each row is one independent acceptance unit. Commands and runtime receipts are pending Architecture/implementation binding; no execution is claimed.

| ID | Exact source | Trigger | Observable behavior | Success / rejection | Independent witness | Acceptance / capability |
| --- | --- | --- | --- | --- | --- | --- |
| AO-01a | FR-1 missing target | absent path | reject invalid-input | absent-path fixture | pending independent witness | A03/CAP-1/pending independent witness |
| AO-01b | FR-1 non-directory | file path | reject invalid-input | file-target fixture | pending independent witness | A03/CAP-1/pending independent witness |
| AO-01c | FR-1 escaping | traversal path | reject invalid-input | traversal fixture | pending independent witness | A03/CAP-1/pending independent witness |
| AO-02a | FR-1 unsupported | unsupported package | reject/no result | unsupported fixture | pending independent witness | A03/CAP-1/pending independent witness |
| AO-02b | FR-1 minimum set | remove VDD/Acceptance | reject policy reduction | policy-removal fixture | pending independent witness | A04/CAP-1/pending independent witness |
| AO-03a | FR-2 effective target | adapter reads other target | identity-invalid | instrumented adapter | pending independent witness | A06-A07/CAP-1/pending independent witness |
| AO-04a | FR-3 missing validator | validator absent | identity-invalid | missing-validator fixture | pending independent witness | A05-A07/CAP-2/pending independent witness |
| AO-04b | FR-3 substituted validator | undeclared validator | identity-invalid | substitution fixture | pending independent witness | A05-A07/CAP-2/pending independent witness |
| AO-04c | FR-3 escaping validator | root escape | identity-invalid | escape fixture | pending independent witness | A05-A07/CAP-2/pending independent witness |
| AO-05a | FR-3 validator drift | content changes | stale | byte mutation | pending independent witness | A06-A07/CAP-2/pending independent witness |
| AO-05b | FR-3 dependency drift | dependency changes | stale | dependency mutation | pending independent witness | A06-A07/CAP-2/pending independent witness |
| AO-05c | FR-3 incompatibility | contract mismatch | identity-invalid | incompatible fixture | pending independent witness | A06-A07/CAP-2/pending independent witness |
| AO-06a | FR-3 self-selection | candidate selects identity | reject trust | candidate descriptor | pending independent witness | A05-A07/CAP-2/pending independent witness |
| AO-06b | FR-3 forged version | version text only | reject trust | forged output | pending independent witness | A05-A07/CAP-2/pending independent witness |
| AO-06c | FR-3 always-success | all inputs pass | no Replay Result | always-pass validator | pending independent witness | A07/CAP-2/pending independent witness |
| AO-07a | FR-4 positive Probe | valid detached input | pass with bindings | independent valid fixture | pending independent witness | A06-A07/CAP-2/pending independent witness |
| AO-08a | FR-4 negative Probe | declared defect input | fail expected category | malformed fixture; infra controls separate | pending independent witness | A06-A07/CAP-2/pending independent witness |
| AO-09a | FR-5 historical bytes | frozen file write | reject mutation | blob comparison | pending independent witness | A01-A02/CAP-3/pending independent witness |
| AO-09b | FR-5 historical validator | reference inspected | identity auditable | validator blob | pending independent witness | A08/CAP-3/pending independent witness |
| AO-09c | FR-5 original command | command evidence altered | reject alteration | command mutation | pending independent witness | A08/CAP-3/pending independent witness |
| AO-09d | FR-5 wrapper replay | wrapper not launched | reject no-launch | no-launch fixture | pending independent witness | A08/CAP-3/pending independent witness |
| AO-09e | FR-5 replay binding | identity mismatch | reject replay | binding mutation | pending independent witness | A08/CAP-3/pending independent witness |
| AO-09f | FR-5 authority limit | history promoted | reject promotion | forged handoff | pending independent witness | A08/CAP-3/pending independent witness |
| AO-10a | FR-6 seed uniqueness | missing/duplicate seed | reject | cardinality fixture | pending independent witness | A09/CAP-3/pending independent witness |
| AO-10b | FR-6 seed provenance | provenance absent | reject | provenance deletion | pending independent witness | A09/CAP-3/pending independent witness |
| AO-10c | FR-6 seed missing | evidence absent | reject | missing evidence | pending independent witness | A10/CAP-3/pending independent witness |
| AO-10d | FR-6 seed drift | content changes | stale | seed mutation | pending independent witness | A10/CAP-3/pending independent witness |
| AO-10e | FR-6 classification | disallowed class | reject promotion | classification fixture | pending independent witness | A11/CAP-3/pending independent witness |
| AO-10f | FR-6 baseline output | baseline label | reject | baseline-label fixture | pending independent witness | A11/CAP-3/pending independent witness |
| AO-11a | FR-7 Stable provenance | source absent | Stable ineligible | unproven source | pending independent witness | A12/CAP-4/pending independent witness |
| AO-11b | FR-7 Stable immutable | identity changes | stale | identity mutation | pending independent witness | A12/CAP-4/pending independent witness |
| AO-12a | FR-8 valid case | one side missing | aggregate reject | missing-side fixture | pending independent witness | A12/CAP-4/pending independent witness |
| AO-12b | FR-8 invalid case | copied output | aggregate reject | copy fixture | pending independent witness | A12/CAP-4/pending independent witness |
| AO-12c | FR-8 historical case | relabelled case | aggregate reject | relabel fixture | pending independent witness | A12/CAP-4/pending independent witness |
| AO-13a | FR-9 workflow consumer | route unreachable | closure reject | unreachable fixture | pending independent witness | A13/CAP-5/pending independent witness |
| AO-13b | FR-9 VDD consumer | omitted caller | closure reject | omission fixture | pending independent witness | A13/CAP-5/pending independent witness |
| AO-13c | FR-9 Acceptance consumer | omitted caller | closure reject | omission fixture | pending independent witness | A13/CAP-5/pending independent witness |
| AO-14a | FR-10 enable | approved candidate | real Candidate call | no-call fixture | pending independent witness | A15/CAP-5/pending independent witness |
| AO-14b | FR-10 disable | candidate enabled | real Prior call | config-only fixture | pending independent witness | A15/CAP-5/pending independent witness |
| AO-14c | FR-10 rollback | rollback applicable | Prior identity/verdict/category restored | rejection-only fixture | pending independent witness | A15/CAP-5/pending independent witness |
| AO-14d | FR-10 re-enable | candidate current | real Candidate call | skip fixture | pending independent witness | A15/CAP-5/pending independent witness |
| AO-15a | FR-11 Exact Cover | coverage built | no orphan nodes | orphan mapping fixture | pending independent witness | A01-A17/CAP-6/pending independent witness |
| AO-16a | FR-12 snapshot | bound input changes | reproduce or stale | reconstruction mutation | pending independent witness | A06/A08/CAP-7/pending independent witness |
| AO-17a | FR-13 authorization | non-empty auth | reject publication | forged auth | pending independent witness | A14/CAP-8/pending independent witness |
| AO-17b | FR-13 lifecycle | foreign state | reject publication | foreign-state fixture | pending independent witness | A14/CAP-8/pending independent witness |
| AO-18a | NFR-1 fail closed | unknown fact | unsuccessful terminal | corrupt fact | pending independent witness | NFR-1/CAP-6/pending independent witness |
| AO-18b | NFR-2 auditability | missing trace | evidence-invalid | binding deletion | pending independent witness | NFR-2/CAP-6/pending independent witness |
| AO-18c | NFR-3 reproducibility | fresh mismatch | fail closed | fresh checkout | pending independent witness | NFR-3/CAP-7/pending independent witness |
| AO-18d | NFR-4 isolation | shared mutable evidence | reject | cross-case substitution | pending independent witness | NFR-4/CAP-4/pending independent witness |
| AO-18e | NFR-5 immutability | historical mutation | reject write | rename/delete attempt | pending independent witness | NFR-5/CAP-3/pending independent witness |
| AO-18f | NFR-6 platform | profile authority/path mismatch | reject | Windows/profile fixture | pending independent witness | NFR-6/CAP-1/pending independent witness |
| AO-18g | NFR-7 bounded | timeout/output limit | unsuccessful; coverage unchanged | timeout fixture | pending independent witness | NFR-7/CAP-4/pending independent witness |
| AO-18h | Guardrail installed paths | write protected BMAD/GDS | reject write | protected-path fixture | pending independent witness | A16/CAP-8/pending independent witness |
| AO-18i | Guardrail no alternate directory | new TC-D1 tree | reject scope | directory-injection fixture | pending independent witness | TC-D1-001/CAP-8/pending independent witness |
| AO-18j | Guardrail Skill-input | redesign v1/current pointer | reject scope | protocol-change fixture | pending independent witness | TC-D1-002/CAP-8/pending independent witness |
| AO-18k | Guardrail real RED tests | production change without defect test | reject change | missing-RED fixture | pending independent witness | guardrail/CAP-6/pending independent witness |
| AO-18l | A16 Phase boundary | Phase file write | reject write | Phase fixture | pending independent witness | A16/CAP-8/pending independent witness |
| AO-18m | A16 runtime boundary | runtime file write | reject write | runtime fixture | pending independent witness | A16/CAP-8/pending independent witness |
| AO-18n | A16 Hosted workspace | workspace write | reject write | workspace fixture | pending independent witness | A16/CAP-8/pending independent witness |
| AO-18o | A16 account boundary | account write | reject write | account fixture | pending independent witness | A16/CAP-8/pending independent witness |
| AO-18p | A16 sandbox boundary | sandbox write | reject write | sandbox fixture | pending independent witness | A16/CAP-8/pending independent witness |
| AO-18q | A17 roadmap separation | TC-E0/D2-D6 work | reject scope | roadmap fixture | pending independent witness | A17/CAP-8/pending independent witness |
| AO-18r | A17 no promotion | promotion requested | reject | promotion fixture | pending independent witness | A17/CAP-8/pending independent witness |
| AO-18s | A17 no Miner/Curator | feature requested | reject | feature fixture | pending independent witness | A17/CAP-8/pending independent witness |
| AO-18t | A17 no autonomous/ranking/RL | autonomy requested | reject | autonomy fixture | pending independent witness | A17/CAP-8/pending independent witness |
| AO-03b | FR-3 successful receipt provenance | validator executes successfully | receipt records trusted content identity and descriptive validator version | remove version/content fields | pending independent witness | A06/CAP-2/pending independent witness |
| AO-10g | FR-6 seed applicability | seed applicability omitted or false | seed record rejected | applicability deletion fixture | pending independent witness | A09/CAP-3/pending independent witness |
| AO-10h | FR-6 seed missing label | missing label omitted | seed record rejected | missing-label fixture | pending independent witness | A10/CAP-3/pending independent witness |
| AO-10i | FR-6 seed counterexample | counterexample/explicit absence omitted | seed record rejected | counterexample deletion fixture | pending independent witness | A10/CAP-3/pending independent witness |
| AO-18u | New PRD guardrail no replacement tree | alternate TC-D1 directory created | scope rejected | directory-injection fixture | pending independent witness | guardrail/CAP-8/pending independent witness |
| AO-18v | New PRD guardrail Skill-input v2 | v1/current-pointer redesign proposed | scope rejected | protocol-redesign fixture | pending independent witness | guardrail/CAP-8/pending independent witness |
| AO-18w | New PRD guardrail defect-revealing tests | production change lacks prior real RED test | change rejected | missing-RED fixture | pending independent witness | guardrail/CAP-6/pending independent witness |
| AO-12d1 | FR-8 dirty baseline | undeclared baseline change | contamination rejected | dirty-baseline fixture | A12 | CAP-4/A12 |
| AO-12d2 | FR-8 knowledge collision | read-set self-collision | collision rejected | collision fixture | A12 | CAP-4/A12 |
| AO-12d3 | FR-8 policy/index gap | required relation absent | fail closed | policy-gap fixture | A12 | CAP-4/A12 |

## Bidirectional mapping
Every effective FR consequence, NFR, guardrail, and retained A01-A17 duty maps to dedicated rows above, and every row names its exact source and acceptance/capability. Mapping is many-to-many only where the witness independently observes each duty. Historical mapping: A01→AO-09a; A02→AO-09a; A03→AO-01a/b/c,AO-02a,AO-03a; A04→AO-02b,AO-13b/c; A05→AO-04a/b/c,AO-06a/b; A06→AO-03a,AO-03b,AO-05a/b/c,AO-07a,AO-08a; A07→AO-01a through AO-08a; A08→AO-09b/c/d/e/f; A09→AO-10a/b,AO-10g; A10→AO-10c/d,AO-10h/i; A11→AO-10e/f; A12→AO-11a/b,AO-12a/b/c,AO-12d1/d2/d3; A13→AO-13a/b/c; A14→AO-17a/b; A15→AO-14a/b/c/d; A16→AO-16a plus AO-18h,l–p; A17→AO-18q–t. Guardrails map to AO-18u/v/w.
