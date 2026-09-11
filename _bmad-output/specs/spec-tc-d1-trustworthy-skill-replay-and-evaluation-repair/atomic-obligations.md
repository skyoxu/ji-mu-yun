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
