# Immutable-main Acceptance completion

Completed at 2026-10-26T19:38:33.902649+00:00. The public Coordinator exited 0 and returned `completed`; its owner finalization authorizes `acceptance-passed`. This is a native Acceptance result, not publication or release authority.

- Candidate commit: `d82a2385a07672117eda6c6c90c6df4527d3bf45`; tree: `cbfb0d5f369aa2287abe56ee626d9525c0083773`.
- Actual main trust root remains `a1e783c569cb5a78ea8728c83518fd13c73a99e8`.
- Current plan: `execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings`; bytes: `sha256:aab95b0036eea778b6651714309c7f9e8d005b0eeabfd07185cf6584cd825c7e`. The 305 obligations/acceptances and approved scope are unchanged.
- Persisted run: `execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings/acceptance-runs/acceptance-27cbb872d11fa729`.

## Repair and trust boundary

Five source files add a private immutable-main validator worker, use it from the Knowledge context caller, cover its failure paths, correct the composition fixture preparation order, and document the supported operation. The actual resolved main Git objects remain the only validator trust source. Candidate modules are never imported by that worker. No selectable external validator, main rewrite, account/system permission change, or new trust protocol was added. Main drift, unsafe/ambiguous roots, unsupported imports, invalid responses and missing originals fail closed.

- `.agents/skills/run-refactor-implementation-acceptance/scripts/knowledge_context.py`
- `.agents/skills/run-refactor-implementation-acceptance/scripts/trusted_knowledge_validator.py`
- `.agents/skills/run-refactor-implementation-acceptance/tests/test_trusted_knowledge_validator.py`
- `.agents/skills/run-refactor-implementation-acceptance/tests/test_current_acceptance_closeout.py`
- `.agents/skills/run-refactor-implementation-acceptance/references/prepare-and-run.md`

## Tests and compatibility evidence

- Final focused run: 33 cases and 4 subtests passed (37 JUnit entries), zero failure/error/skip. Raw `GREEN-final-focused.xml` is retained. Actual RED evidence includes the old byte-match rejection and the nested self-authored main root acceptance.
- The 11 remaining composed compatibility cases all passed. The separately completed positive smoke passed in 218.253 seconds. Their individual raw JUnit files and source epochs are recorded in `compatibility-source-scope.json` and `FINAL-STATUS.json`.
- The original batch has 35 passing top-level checks plus 22 subtests and 12 fixture/input-invalidating failures. Those failures remain in `compatibility.xml`; it is not represented as an all-pass final-source run. The 35 unchanged checks were reused instead of rerun.
- The first corrected batch has three successes and a preserved failure during concurrent fixture-source activity; existing evidence does not prove that timing overlap was the unique cause. The serial successor passes are the positive evidence. A separate basetemp-parent setup failure is retained and is not business RED.
- Two actual fixture frontier comparisons differ in environment and Knowledge publication/input bytes; their expensive frontiers cannot safely share an exact execution identity. No cache receipt was converted.
- The final candidate registered action re-executed the relevant small routing/context/worker checks: 42 cases and 26 subtests passed in 11.28 seconds. The other three registered actions also exited 0.

### Remaining compatibility case durations

| Case | Successful execution seconds | Cumulative retry seconds where recorded |
| --- | ---: | ---: |
| `test_current_handoff_preserves_crlf_catalog_bytes_with_user_autocrlf` | 172.150 | No retry in this case record |
| `test_current_q8_projection_and_real_coordinator_close_and_replay[present1]` | 648.342 | No retry in this case record |
| `test_current_q8_projection_and_real_coordinator_close_and_replay[present2]` | 553.306 | No retry in this case record |
| `test_failed_acceptance_action_stops_once_and_cannot_borrow_q8_pass` | 455.910 | 845.558 |
| `test_q8_replay_rejects_source_and_deferred_drift` | 428.415 | 472.007 |
| `test_coordinator_replay_rejects_changed_owned_evidence[final]` | 507.942 | 546.934 |
| `test_coordinator_replay_rejects_changed_owned_evidence[events]` | 579.482 | 623.796 |
| `test_coordinator_replay_rejects_changed_owned_evidence[registry]` | 525.039 | 566.428 |
| `test_coordinator_replay_rejects_changed_owned_evidence[prepared]` | 513.787 | 554.719 |
| `test_coordinator_replay_rejects_changed_owned_evidence[context]` | 509.583 | 550.013 |
| `test_explicit_review_request_returns_handoff_without_actions_or_bootstrap` | 433.634 | 473.389 |

## Native closure and reuse

- All 12 current Q7/terminal results passed, with 610 runtime closure tuples.
- Exactly 29 new positive process executions and 15375 case executions were needed. All have exit 0 and no timeout. These are affected dependency refreshes, not failures of the business TDD cycle.
- All 12 existing probe originals were transported byte-for-byte and accepted through native reentry. Historical causal RED, unchanged owner tests and the real Windows subset retain their actual limited scope; they were not rerun or relabeled.
- Prior positive proofs bind changed Knowledge caller/source and completed Skill-input attempt dependencies. They cannot be safely rebound. The refresh was caused by those real dependency changes, not a Git SHA change alone.
- Completed Skill-input attempt files are retained in their original `.skill-input-work` location and must accompany external review/publication. Do not move/delete them as temporary garbage.
- Q8 only revalidates proof; the projection, preparation and Coordinator owner checks replay existing originals without rerunning the 29 business stages.

| Public native command | Exit | Seconds |
| --- | ---: | ---: |
| Quick Dev `implementation-complete` | 0 | 547.401 |
| Acceptance `project-compact-vdd` | 0 | 558.315 |
| Acceptance `prepare-run` | 0 | 545.036 |
| Acceptance `run-coordinator` | 0 | 601.698 |

## Raw result entrypoints

- Q8: `logs/acceptance-main-isolated-proof-refresh-20261026/Q8/implementation-complete-result.v2.json`; `sha256:b21898dbe0a58b558a1ac80d602491285d5a8b9170f5cb4f962a6f50c45a85a2`.
- Coordinator: `execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings/acceptance-inputs/acceptance-20261026-main-isolated/acceptance-coordinator-result.v4.json`; `sha256:0df6297acf086696af1c271c2bec96c47127493fa2cb129a1e4f50b395e80395`.
- Final authorization: `execution-plans/2026-10-26-vdd-knowledge-query-p1-static-bindings/acceptance-runs/acceptance-27cbb872d11fa729/finalization/acceptance-passed.v1.json`; `sha256:13d958d223426a92d6f281bcbadcfb14c4833cfee11747b0877becaece75acd8`.
- Exact native argv, stdout/stderr and unit ledgers remain alongside these logs. `FINAL-STATUS.json` maps the per-process originals; `EVIDENCE-INDEX.json` indexes current local handoff files. It is an index, not a substituted execution receipt.

## Limits and handoff

- No new model, BMAD, external A/B/reviewer, Windows execution, CI monitoring, push, PR, merge or main change was performed. The four native deterministic actions do not launch Bootstrap; `bootstrapInvoked=false` and `typedHandoff=null`.
- Existing Windows evidence remains 11 platform nodes only. It does not prove all Windows Acceptance behavior, the seven P1 cases on Windows, or the new isolated worker on Windows.
- Prior disclosed legacy fixture/Windows long-path limits remain. This targeted result is not a claim every repository test ran or has zero regression risk.
- Earlier independent review GO applied to its fixed prior candidate. The five-file loader change has production tests and this native Acceptance result; independent narrow review/publication remains the parent handoff responsibility, not a claimed old-review approval.
- The candidate source is committed locally; owner-generated `acceptance-current.v1.json` and `acceptance-runs/` are untracked outputs retained for delivery. No original workspace/evidence was reset or deleted.
- Owned serial drivers have exited. Source hash guards and the actual main identity matched at completion. No further implementation or execution starts from this report.
