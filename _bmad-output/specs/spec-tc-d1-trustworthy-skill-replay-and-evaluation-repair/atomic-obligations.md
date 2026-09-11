# TC-D1 Atomic Obligation Register

Each row is an independent acceptance unit. Commands and runtime receipts are pending Architecture/implementation binding; no execution is claimed.

| ID | Exact source | Trigger | Observable behavior | Success / rejection | Independent witness | Acceptance / capability |
| --- | --- | --- | --- | --- | --- | --- |
| AO-01a | FR-1 missing target | absent path | reject invalid-input | absent-path fixture | A03/CAP-1 |
| AO-01b | FR-1 non-directory | file path | reject invalid-input | file-target fixture | A03/CAP-1 |
| AO-01c | FR-1 escaping | traversal path | reject invalid-input | traversal fixture | A03/CAP-1 |
| AO-02a | FR-1 unsupported | unsupported package | reject/no result | unsupported fixture | A03/CAP-1 |
| AO-02b | FR-1 minimum set | remove VDD/Acceptance | reject policy reduction | policy-removal fixture | A04/CAP-1 |
| AO-03a | FR-2 effective target | adapter reads other target | identity-invalid | instrumented adapter | A06-A07/CAP-1 |
| AO-04a | FR-3 missing validator | validator absent | identity-invalid | missing-validator fixture | A05-A07/CAP-2 |
| AO-04b | FR-3 substituted validator | undeclared validator | identity-invalid | substitution fixture | A05-A07/CAP-2 |
| AO-04c | FR-3 escaping validator | root escape | identity-invalid | escape fixture | A05-A07/CAP-2 |
| AO-05a | FR-3 validator drift | content changes | stale | byte mutation | A06-A07/CAP-2 |
| AO-05b | FR-3 dependency drift | dependency changes | stale | dependency mutation | A06-A07/CAP-2 |
| AO-05c | FR-3 incompatibility | contract mismatch | identity-invalid | incompatible fixture | A06-A07/CAP-2 |
| AO-06a | FR-3 self-selection | candidate selects identity | reject trust | candidate descriptor | A05-A07/CAP-2 |
| AO-06b | FR-3 forged version | version text only | reject trust | forged output | A05-A07/CAP-2 |
| AO-06c | FR-3 always-success | all inputs pass | no Replay Result | always-pass validator | A07/CAP-2 |
| AO-07a | FR-4 positive Probe | valid detached input | pass with bindings | independent valid fixture | A06-A07/CAP-2 |
| AO-08a | FR-4 negative Probe | declared defect input | fail expected category | malformed fixture; infra controls separate | A06-A07/CAP-2 |
| AO-09a | FR-5 historical bytes | frozen file write | reject mutation | blob comparison | A01-A02/CAP-3 |
| AO-09b | FR-5 historical validator | reference inspected | identity auditable | validator blob | A08/CAP-3 |
| AO-09c | FR-5 original command | command evidence altered | reject alteration | command mutation | A08/CAP-3 |
| AO-09d | FR-5 wrapper replay | wrapper not launched | reject no-launch | no-launch fixture | A08/CAP-3 |
| AO-09e | FR-5 replay binding | identity mismatch | reject replay | binding mutation | A08/CAP-3 |
| AO-09f | FR-5 authority limit | history promoted | reject promotion | forged handoff | A08/CAP-3 |
| AO-10a | FR-6 seed uniqueness | missing/duplicate seed | reject | cardinality fixture | A09/CAP-3 |
| AO-10b | FR-6 seed provenance | provenance absent | reject | provenance deletion | A09/CAP-3 |
| AO-10c | FR-6 seed missing | evidence absent | reject | missing evidence | A10/CAP-3 |
| AO-10d | FR-6 seed drift | content changes | stale | seed mutation | A10/CAP-3 |
| AO-10e | FR-6 classification | disallowed class | reject promotion | classification fixture | A11/CAP-3 |
| AO-10f | FR-6 baseline output | baseline label | reject | baseline-label fixture | A11/CAP-3 |
| AO-11a | FR-7 Stable provenance | source absent | Stable ineligible | unproven source | A12/CAP-4 |
| AO-11b | FR-7 Stable immutable | identity changes | stale | identity mutation | A12/CAP-4 |
| AO-12a | FR-8 valid case | one side missing | aggregate reject | missing-side fixture | A12/CAP-4 |
| AO-12b | FR-8 invalid case | copied output | aggregate reject | copy fixture | A12/CAP-4 |
| AO-12c | FR-8 historical case | relabelled case | aggregate reject | relabel fixture | A12/CAP-4 |
| AO-12d | FR-8 dirty/collision/index | invariant violated | aggregate reject | per-case fault fixtures | A12/CAP-4 |
| AO-13a | FR-9 workflow consumer | route unreachable | closure reject | unreachable fixture | A13/CAP-5 |
| AO-13b | FR-9 VDD consumer | omitted caller | closure reject | omission fixture | A13/CAP-5 |
| AO-13c | FR-9 Acceptance consumer | omitted caller | closure reject | omission fixture | A13/CAP-5 |
| AO-14a | FR-10 enable | approved candidate | real Candidate call | no-call fixture | A15/CAP-5 |
| AO-14b | FR-10 disable | candidate enabled | real Prior call | config-only fixture | A15/CAP-5 |
| AO-14c | FR-10 rollback | rollback applicable | Prior identity/verdict/category restored | rejection-only fixture | A15/CAP-5 |
| AO-14d | FR-10 re-enable | candidate current | real Candidate call | skip fixture | A15/CAP-5 |
| AO-15a | FR-11 Exact Cover | coverage built | no orphan nodes | orphan mapping fixture | A01-A17/CAP-6 |
| AO-16a | FR-12 snapshot | bound input changes | reproduce or stale | reconstruction mutation | A06/A08/CAP-7 |
| AO-17a | FR-13 authorization | non-empty auth | reject publication | forged auth | A14/CAP-8 |
| AO-17b | FR-13 lifecycle | foreign state | reject publication | foreign-state fixture | A14/CAP-8 |
| AO-18a | NFR-1 fail closed | unknown fact | unsuccessful terminal | corrupt fact | NFR-1/CAP-6 |
| AO-18b | NFR-2 auditability | missing trace | evidence-invalid | binding deletion | NFR-2/CAP-6 |
| AO-18c | NFR-3 reproducibility | fresh mismatch | fail closed | fresh checkout | NFR-3/CAP-7 |
| AO-18d | NFR-4 isolation | shared mutable evidence | reject | cross-case substitution | NFR-4/CAP-4 |
| AO-18e | NFR-5 immutability | historical mutation | reject write | rename/delete attempt | NFR-5/CAP-3 |
| AO-18f | NFR-6 platform | profile authority/path mismatch | reject | Windows/profile fixture | NFR-6/CAP-1 |
| AO-18g | NFR-7 bounded | timeout/output limit | unsuccessful; coverage unchanged | timeout fixture | NFR-7/CAP-4 |
| AO-18h | Guardrail installed paths | write protected BMAD/GDS | reject write | protected-path fixture | A16/CAP-8 |
| AO-18i | Guardrail no alternate directory | new TC-D1 tree | reject scope | directory-injection fixture | TC-D1-001/CAP-8 |
| AO-18j | Guardrail Skill-input | redesign v1/current pointer | reject scope | protocol-change fixture | TC-D1-002/CAP-8 |
| AO-18k | Guardrail real RED tests | production change without defect test | reject change | missing-RED fixture | guardrail/CAP-6 |
| AO-18l | A16 Phase boundary | Phase file write | reject write | Phase fixture | A16/CAP-8 |
| AO-18m | A16 runtime boundary | runtime file write | reject write | runtime fixture | A16/CAP-8 |
| AO-18n | A16 Hosted workspace | workspace write | reject write | workspace fixture | A16/CAP-8 |
| AO-18o | A16 account boundary | account write | reject write | account fixture | A16/CAP-8 |
| AO-18p | A16 sandbox boundary | sandbox write | reject write | sandbox fixture | A16/CAP-8 |
| AO-18q | A17 roadmap separation | TC-E0/D2-D6 work | reject scope | roadmap fixture | A17/CAP-8 |
| AO-18r | A17 no promotion | promotion requested | reject | promotion fixture | A17/CAP-8 |
| AO-18s | A17 no Miner/Curator | feature requested | reject | feature fixture | A17/CAP-8 |
| AO-18t | A17 no autonomous/ranking/RL | autonomy requested | reject | autonomy fixture | A17/CAP-8 |

| AO-03b | FR-3 successful receipt provenance | validator executes successfully | receipt records trusted content identity and descriptive validator version | remove version/content fields | A06/CAP-2 |
| AO-10g | FR-6 seed applicability | seed applicability omitted or false | seed record rejected | applicability deletion fixture | A09/CAP-3 |
| AO-10h | FR-6 seed missing label | missing label omitted | seed record rejected | missing-label fixture | A10/CAP-3 |
| AO-10i | FR-6 seed counterexample | counterexample/explicit absence omitted | seed record rejected | counterexample deletion fixture | A10/CAP-3 |
| AO-18u | New PRD guardrail no replacement tree | alternate TC-D1 directory created | scope rejected | directory-injection fixture | guardrail/CAP-8 |
| AO-18v | New PRD guardrail Skill-input v2 | v1/current-pointer redesign proposed | scope rejected | protocol-redesign fixture | guardrail/CAP-8 |
| AO-18w | New PRD guardrail defect-revealing tests | production change lacks prior real RED test | change rejected | missing-RED fixture | guardrail/CAP-6 |

## Bidirectional mapping
Every FR consequence, NFR, guardrail, and retained A01-A17 duty maps to one or more rows above; every row names its exact source and acceptance ID. Reuse is many-to-many only when the witness independently observes the listed duty. Historical mapping: A01→AO-09a; A02→AO-09a; A03→AO-01a/b/c,AO-02a,AO-03a; A04→AO-02b,AO-13b/c; A05→AO-04a/b/c,AO-06a/b; A06→AO-03a,AO-05a/b/c,AO-07a,AO-08a; A07→AO-01a–AO-08a; A08→AO-09b/c/d/e/f; A09→AO-10a/b; A10→AO-10c/d; A11→AO-10e/f; A12→AO-11a/b,AO-12a/b/c,AO-12d1/d2/d3; A13→AO-13a; A14→AO-17a/b; A15→AO-14a/b/c/d; A16→AO-18h,l–p; A17→AO-18q–t.
