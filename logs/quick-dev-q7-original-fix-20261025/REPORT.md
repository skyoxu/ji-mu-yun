# Q7 invocation-local original validation repair

Approved scope: user Sentinel_3df2e2fc32b08191b0f693a813b24969, 2026-10-25 14:09 UTC. ADR-0041 applies. Only the Q7 reader, its Q6 reference helper, dedicated tests and bounded reuse explanation were committed; business implementation/tests and unrelated changes were excluded.

Local host commit: 93d06e67b0276ec8cc2e7ae7298aff8ac8e5fbf6, parent b908cb3915cb50c6860445e27c1e1012137e60bb. Not pushed.

## Self-review and implementation

The earlier diagnosis proved repeated original validation and absent internal progress observation, not a historical stack location. Q7 now collects identical originals within one invocation using full descriptor/receipt content, workspace, original/descriptor/receipt paths and filtered environment context. Every edge still rechecks identity, observed/predicate flags, original associations, hashes, case/target/fixture and exact coverage. Full original/request/environment/dependency validation is deferred until before publication, not omitted. Q6's existing validator retains its default behavior; Q7's private callback queues its original checks in the same invocation.

File/inventory-directory metadata seals (including empty directories and absent declared files), environment digest comparison and a second exact native runtime snapshot reject observable changes during validation. The queue has no persistent or cross-call state. This is normal filesystem race detection, not a hermetic defense against privileged restoration of all metadata. No historical receipt/input hash is modified.

Q7 has one content-bound workflow unit. Completed snapshot, edge, Q6 gate and full original checks emit real completion progress; no timer/heartbeat, log touch or polling does so. Progress does not reset total time. Same-unit retries retain the ledger. Default 1800 total/600 idle stays unchanged.

## Targeted validation

- Final targeted-v3: 16 passed in 1.69s, including the two existing native Q7 coverage tests and the new focused cases.
- Existing shared native fixture integration: 1 passed in 14.59s; a tiny deterministic Q7/reference/terminal/closure fixture, not real plan Q8.
- The 139-edge/3-extra-Q6 fixture proves 4 expensive original calls and 1 native Q6 gate reread, rather than 556 reconstructions. Other cases cover different original paths, descriptors and profiles, independent edge corruption/association checks, damaged originals, content changes, equal-content file replacement, new/empty-directory inputs, environment/request changes and unchanged total budget after real progress.
- Initial targeted failure was a test fixture creating its second original inside the protected interval; moved setup before validation. Original failed output/XML retained. No gate was weakened to pass it.

## Real S12 public recovery

attempt_s12_recovery.py constructs explicit recovery INPUT solely from original receipt/observation/edge bindings and a current native snapshot; it never writes an accepted result. Public recover exited 0. Subsequent public validate-slice exited 1 with reason reuse-engine-changed. The native shared-execution engine binding conservatively contains changed validation code, so old successful tests cannot be upgraded into current proofs. Original probe/Q6 pass evidence and timeout remain untouched. No budget increase or identical blind retry occurred.

Continuous slice work proceeds under this repaired host in logs/quick-dev-final-slices-20261025-v5 with frozen business inputs and public actions. The S2 test guard recognizes only the exact approved four-file child commit, retaining its prior exact six-/two-file ancestry guards and original publication inventory. This is a legitimate test-only Q2 update, not a plan/oracle change. Old nine terminal snapshots are preserved as history; new native proof must satisfy current host identity. No new model author requests, BMAD skill, reviewer, external A/B, whole-plan Q8, Acceptance, publication or CI monitoring is authorized/performed.
