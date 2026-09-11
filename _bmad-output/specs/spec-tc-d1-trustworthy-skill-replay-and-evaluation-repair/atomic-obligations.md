# TC-D1 Atomic Obligation Register

This normative register is the executable planning contract. No listed test or
receipt is claimed to have run; command and evidence bindings remain pending
Architecture and implementation.

| ID | Source | Trigger | Observable behavior | Success / rejection | Independent witness | Acceptance / capability |
| --- | --- | --- | --- | --- | --- | --- |
| AO-01 | FR-1 missing/non-directory/escaping target | request invalid target | reject before validation | no Replay Result / reject | one fixture per invalidity | A03, CAP-1 |
| AO-02 | FR-1 unsupported/minimum target | unsupported request | reject and retain VDD/Acceptance minimum | unsupported success rejected | unsupported-target fixture | A03/A04, CAP-1 |
| AO-03 | FR-2 wrong effective target | validator runs other package | identity mismatch fails | recorded target alone rejected | instrumented wrong-target adapter | A06/A07, CAP-1 |
| AO-04 | FR-3 missing/substituted/escaping validator | capability resolution | fail closed | no trusted result | separate missing, substitution, escape fixtures | A05-A07, CAP-2 |
| AO-05 | FR-3 drift/incompatibility/dependency closure | bound input changes | stale/invalid result | drift cannot pass | independent validator/dependency mutation witnesses | A06/A07, CAP-2 |
| AO-06 | FR-3 self-selection/version/always-success | candidate controls identity or validator always passes | reject trust | self-report/always-pass cannot succeed | self-approval and always-success fixtures | A05-A07, CAP-2 |
| AO-07 | FR-4 positive Probe | valid detached Probe | real command passes | pass with bound evidence | independently materialized valid fixture | A06/A07, CAP-2 |
| AO-08 | FR-4 negative Probe | invalid detached Probe | declared defect/category failure | infrastructure failure is not negative success | malformed fixture plus timeout/import/missing-dependency controls | A06/A07, CAP-2 |
| AO-09 | FR-5 historical immutability | replay round | historical bytes unchanged; current replay states limits | mutation or authority promotion rejected | frozen historical blob comparison | A01/A02/A08, CAP-3 |
| AO-10 | FR-6 seed provenance | three named seeds | each exactly once, non-baseline classification | missing/drift/promotion rejected | per-seed identity and counterexample witness | A09-A11, CAP-3 |
| AO-11 | FR-7 stable eligibility | comparison run | source-supported Stable identity and real Candidate change | temporary/unproven Stable rejected | provenance and immutable identity check | A12, CAP-4 |
| AO-12 | FR-8 six-case two-sided execution | matrix run | each case distinct, both subjects execute | skip/duplicate/relabel/copy/wrong-target fails | per-case launch receipts and mutation controls | A12, CAP-4 |
| AO-13 | FR-9 complete Consumers | manifest frozen | all callers, including VDD/Acceptance/workflow routing, execute | omission/unreachable route fails | call-surface reconciliation | A13, CAP-5 |
| AO-14 | FR-10 enable/disable/rollback/re-enable | route exercise | real calls and restored baseline | config-only or candidate rejection fails | per-transition Consumer fixtures | A15, CAP-5 |
| AO-15 | FR-11 Exact Cover | coverage build | bidirectional source/assertion/evidence graph | orphan or aggregate-only assertion fails | per-AO witness mapping | A01-A17, CAP-6 |
| AO-16 | FR-12 snapshot freshness | fresh checkout or bound input change | reproduce or invalidate | unexplained drift fails closed | snapshot mutation/reconstruction pair | A06/A08, CAP-7 |
| AO-17 | FR-13 authority separation | derived artifact publication | empty authorization and proper lifecycle handoff | foreign state, old Q8, assistant prose rejected | forged authorization/state fixture | A14, CAP-8 |
| AO-18 | NFR-1..NFR-7 and guardrails | any run | fail-closed, auditable, reproducible, isolated, immutable, Windows-capable, bounded | unknown/timeout/forbidden write fails | one violation witness per NFR/guardrail retained for Architecture binding | A16/A17, CAP-6/CAP-8 |

### Bidirectional mapping rule

Every FR consequence, NFR, guardrail, and retained A01-A17 duty must map to one
or more AO rows; every AO row maps back to its exact source and acceptance ID.
Many-to-many reuse is valid only where the row states why the witness observes
that duty independently. Concrete commands, selectors, and runtime receipts are
**pending binding**, never implied by this register.

## Atomic Sub-obligations

The AO rows above are groups only. These stable sub-IDs are the individually
accepted units; each has its own witness and verdict. Concrete commands remain
pending Architecture/implementation binding.

| ID | Exact source | Trigger and observable behavior | Success / rejection | Independent witness | Acceptance / capability |
| --- | --- | --- | --- | --- | --- |
| AO-04a | FR-3 missing validator | resolver cannot locate validator | identity-invalid; no trusted result | remove validator fixture | A05-A07 / CAP-2 |
| AO-04b | FR-3 substituted validator | resolver selects undeclared validator | substitution rejected | alternate-content fixture | A05-A07 / CAP-2 |
| AO-04c | FR-3 escaping validator | resolved path escapes approved root | escape rejected | traversal fixture | A05-A07 / CAP-2 |
| AO-05a | FR-3 content drift | bound validator content changes | stale/identity-invalid | mutate validator bytes | A06-A07 / CAP-2 |
| AO-05b | FR-3 dependency drift | semantic dependency changes | stale/identity-invalid | mutate one dependency | A06-A07 / CAP-2 |
| AO-05c | FR-3 incompatibility | validator does not satisfy contract | incompatible rejected | incompatible capability fixture | A06-A07 / CAP-2 |
| AO-06a | FR-3 candidate self-selection | candidate chooses validator identity | self-selection rejected | candidate-controlled descriptor | A05-A07 / CAP-2 |
| AO-06b | FR-3 self-reported version | only version text supports trust | trust not established | forged version output | A05-A07 / CAP-2 |
| AO-06c | FR-3 always-success validator | validator passes every input | no successful Replay Result | always-pass implementation with invalid Probe | A07 / CAP-2 |
| AO-09a | NFR-5, A01-A02 historical bytes | repair run writes frozen file | mutation rejected | frozen blob comparison | A01-A02 / CAP-3 |
| AO-09b | FR-5, A08 historical authority | historical result used as current authority | authority promotion rejected | forged historical acceptance handoff | A08 / CAP-3 |
| AO-18a | NFR-1 fail-closed | unknown/missing/stale/ambiguous fact | unsuccessful terminal state | delete or corrupt bound fact | NFR-1 / CAP-6 |
| AO-18b | NFR-2 auditability | verdict lacks traceable identity/evidence | evidence-invalid | remove one binding edge | NFR-2 / CAP-6 |
| AO-18c | NFR-3 reproducibility | fresh checkout differs semantically | reproduction fails closed | reconstruct from pinned inputs | NFR-3 / CAP-7 |
| AO-18d | NFR-4 isolation | mutable evidence shared across subjects/cases | aggregate rejected | cross-case evidence substitution | NFR-4 / CAP-4 |
| AO-18e | NFR-5 historical immutability | frozen tracked member changed | write rejected | attempt rename/delete/byte mutation | NFR-5 / CAP-3 |
| AO-18f | NFR-6 platform boundary | unsupported platform behavior or profile authority | compatibility/authority rejected | Windows path and profile-source fixtures | NFR-6 / CAP-1 |
| AO-18g | NFR-7 bounded execution | timeout/output budget exhausted | execution unsuccessful; coverage unchanged | timeout and oversized-output fixtures | NFR-7 / CAP-4 |
| AO-18h | Guardrail installed files | write targets `_bmad/**`, `bmad-*`, or `gds-*` | forbidden write rejected | protected-path write attempt | guardrail/A16 / CAP-8 |
| AO-18i | Guardrail roadmap separation | TC-E0 or D2-D6 scope introduced | out-of-scope change rejected | scope-injection fixture | guardrail/A17 / CAP-8 |
| AO-18j | Guardrail no promotion/autonomy | seed/package/skill promoted or autonomous mutation requested | promotion rejected | promotion/autonomous-change fixture | guardrail/A17 / CAP-8 |

### Historical one-to-one expansion

| Historical duty | Dedicated obligation |
| --- | --- |
| A03 | AO-01, AO-02, AO-03 |
| A04 | AO-02, AO-13 |
| A05 | AO-04a, AO-04b, AO-04c, AO-06a, AO-06b |
| A06 | AO-03, AO-05a, AO-05b, AO-05c, AO-07, AO-08 |
| A07 | AO-01 through AO-08, with each witness kept distinct by trigger |
| A08 | AO-09b |
| A09 | AO-10 seed identity/provenance checks |
| A10 | AO-10 missing/drift checks |
| A11 | AO-10 classification checks |
| A12 | AO-11, AO-12 |
| A13 | AO-13 workflow-model-routing observation |
| A14 | AO-17 |
| A15 | AO-14 transition sub-obligations |
| A16 | AO-18h plus boundary obligations in AO-18e |
| A17 | AO-18i, AO-18j |

Each mapping is bidirectional: the historical duty names its dedicated AO and
each AO names its exact historical source. A missing, substituted, escaping,
drifted, or incompatible witness therefore cannot be represented by a generic
"file missing" result.
