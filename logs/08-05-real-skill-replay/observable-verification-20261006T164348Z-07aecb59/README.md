# Windows observable replay verification

- HEAD: `69bb7f87e28a67ee7a017d805088e2ecff7d5d35`
- Scope: the three original selectors; 340 collected tests.
- Unittest: 32 passed, no failures or errors.
- Pytest: incomplete and unsuccessful. 46 nodes finished before the active
  node `scripts/sc/tests/tc_d1_cer/test_s17.py::test_detached_replay_binds_input_and_output_to_same_probe_identity`
  exceeded the 300-second per-test budget.
- Cleanup: the verifier terminated only its owned Windows process tree and
  recorded termination stdout/stderr.
- JUnit: no genuine JUnit was produced because pytest was terminated during the
  timed-out node. No synthetic JUnit is included.

The directory intentionally retains the summary, selected node manifest,
collection and test events, traceback stack dumps, process results, native
stdout/stderr, and termination output. C3 remains OPEN; this is verification
evidence only and does not establish Acceptance readiness.
