# Round 5: Real Skill Replay Repair

This append-only round reopens `RMAP-S0`, `RMAP-S2`, and `RMAP-S3` after the
external review in `docs/fix80501.txt`. Earlier implementation and Acceptance
artifacts remain historical evidence and do not authorize this repair.

The repair requires an explicitly bound target, a content-bound validator,
real positive and negative executions, executable matrix cases, and fail-closed
disabled or rolled-back capabilities. Completion evidence must contain observed
process exit codes and output hashes from the current worktree.

## Observed Results

- The isolated `main` implementation produced a nonzero RED result in
  `logs/08-05-real-skill-replay/red-baseline/observation.v1.json`.
- Targeted replay and Acceptance package tests executed 17 cases successfully;
  JUnit output is `logs/08-05-real-skill-replay/targeted-junit.xml`.
- Direct package and matrix replay process outputs are preserved under
  `logs/08-05-real-skill-replay/direct-replays/`.
- Current Quick Dev observed all seven bound cases as `present`, then executed
  regression and terminal stages. Its Q8 result is
  `logs/08-05-real-skill-replay/quick-dev/current-run-6-completion/implementation-complete.v2.json`.
- The historical plan-local implementation validator remains non-authoritative
  for this repair. Its VDD-wide unittest command currently fails in
  `test_vdd_knowledge_preflight.py` because that historical test supplies a v1
  Skill-input receipt to a consumer that now requires a v2 current pointer.
- Independent Refactor Acceptance reached the live Skill-input v2 gate. A RED
  regression exposed that the plan root was incorrectly treated as a payload
  directory; the consumer contract now marks `implementation_target` as
  non-payload, and the combined replay suite passes 18 tests. The next live
  preparation terminates with the typed `review-required` route because the
  candidate changes Skill and Knowledge-owned files. The append-only blocker
  is `logs/08-05-real-skill-replay/acceptance-round5/skill-input-blocker.v1.json`.
