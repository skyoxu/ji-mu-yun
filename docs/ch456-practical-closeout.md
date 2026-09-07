# CH456 Practical Closeout and Current Operating Rules

Decision date: 2026-09-07. Authority: maintainer-approved practical closeout,
recorded in [ADR-0041](adr/ADR-0041-bootstrap-review-execution-control-plane-ownership.md).
This is an operating decision and evidence index, not generated acceptance evidence.

## Scope and precedence

The accepted goal is practical fidelity to the original behavior and process:
complete requirement coverage, feasible slices, real RED/GREEN/REFACTOR,
bounded failure handling and deterministic terminal closure. Literal reproduction
of every draft algorithm is not required.

For the topics below, this decision supersedes the earlier operating wording in
the [source draft](vdd-quick-dev-chapter-4-5-6-capability-upgrade-draft.md),
the 2026-08-31 PRD/addendum, and the CH456 canonical Spec companions.
Frozen source packages, canonical selections and historical evidence remain
unchanged. All other truth-floor requirements continue to apply.

| Topic | Current adopted rule | Earlier wording disposition |
| --- | --- | --- |
| Atomic semantics and V6 cohesion | Each active obligation retains its own Acceptance oracle/assertions. Group compatible implementation work by owner and lane, with dependency and write/forbidden boundaries. Preserve individual transitions, predicates and evidence. | Spec execution-protocol V6 and implementation-contracts stable slice ID wording are superseded where they require splitting solely by failure family, state-transition text or evidence paths. This is not permission to merge incompatible execution contracts. |
| External acceptance | Quick Dev publishes only implementation-complete. External semantic acceptance is a separate, bounded step when requested or required by an applicable policy. Ordinary development does not acquire mandatory heavyweight review. | Draft 18.5, PRD responsibility chain and Spec execution-protocol are qualified by this policy; acceptance-passed remains externally owned and is never implied by Quick Dev completion. |
| Generalization | The fixed FR-301 ledger is an end-to-end regression benchmark. Strict unseen-task generalization is not a prerequisite for this practical closeout; observe it through subsequent real work. | PRD SM-7 and Spec success-metrics unseen-task requirement are deferred for this closeout, not marked satisfied. Repeating FR-301 cannot establish novelty. |
| Critical mutation checks | Every case in the semantic-chain, agent-context and detached structural/family corpora must be rejected; one leak blocks. Final gate checks case dispositions and totals as well as the summary. | Prior 95% mutation thresholds are superseded. Semantic precision/recall thresholds and runtime truth predicates are unchanged. |
| Architecture reconciliation | R19 is a historical Deferred inventory. Its checker passing does not prove current product acceptance. Read the R20 practical reconciliation alongside it. | Preserve R19 and its historical acceptance-blocked entry without treating it as a current live result. |
| Time budgets | Successful runs are meaningful only with their recorded configuration. Reported c6ae33da success used compile=3600s and repair=1200s. | No claim that default 300s repair is proven reliable; no default or live time limit is changed. |

## Implementation and evidence boundaries

Public entries are scripts/vdd/compile_plan.py and scripts/quick_dev/run.py.
Coverage, real execution, same-selector identity, declared write sets, explicit
predecessors and validator-derived completion remain mandatory.

| Evidence | Candidate / state at the audited 7f350aca tree |
| --- | --- |
| Real semantic and deterministic capability metrics | c6ae33da3ff899706603612063643e581be4ae20; committed under logs/ch456-final-acceptance-c6ae33da-r1200 |
| Successful fixed-task live run, Quick Dev regression, 8-25 replay and final seal | Reported locally for c6ae33da; success directory logs/ch456-final-acceptance-c6ae33da-r1200-success was not in the audited remote tree; original files still need archival |
| Full VDD regression after test isolation | 7dc7b8b875eba8c4aeec6533b89967d5364fb734; 242 passed, 58 subtests; logs/ch456-vdd-full-regression-7dc7b8b8 |
| Production equivalence before this closeout | c6ae33da through 7f350aca changed only a test isolation fixture and logs |
| This closeout | Documentation and stricter mutation acceptance only; requires targeted deterministic validation, not a new live run |

The reported successful live run took 2111 seconds with one slice. Until its
original evidence is archived, this remains an attributed local result, not a
new remotely verified claim. The default logs/ch456-final-acceptance completion
file records an older failure and must not be overwritten to manufacture closure.

This closeout does not emit completion JSON, reseal an old candidate as current,
or assert that the revised gate ran a new full live acceptance.

## Remaining local handoff

1. Archive the existing c6ae33da success directory byte-for-byte, preserving
   original source_head, hashes, absolute manifest paths and all failed history.
   A new archive commit does not invalidate the old candidate identity.
   If files are missing, report the gap; do not regenerate them or rerun live.
2. Run only these deterministic tests after synchronizing this change:

~~~powershell
py -3 -m pytest scripts/quick_dev/tests/test_ch456_critical_mutation_thresholds.py .agents/skills/quick-dev-tdd-adapter/tools/tests/test_ch456_final_completion_gate.py -q
~~~

3. Commit the validation output and configuration under a new logs directory.
   Separate the current gate-change validation from historical c6ae33da live
   evidence. Do not rebind the historical evidence to the new commit.

No real-semantic, live-blind or full live final-acceptance invocation is required
for this bounded handoff. No new BMAD cycle is required.

## Stop rule

After archival and targeted validation, close this practical work package.
Future repairs are driven by concrete real-task failures: missed requirements,
false green, illegal writes or inability to close the declared lifecycle.
Wording differences alone do not restart CH456, and this note does not grant
an automatic additional model review or repair round.
