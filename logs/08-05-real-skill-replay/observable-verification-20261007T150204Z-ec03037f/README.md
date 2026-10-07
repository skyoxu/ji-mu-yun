# Windows observable replay verification

- Fixed HEAD: `12e37e9fd2b543ba66e8bebb07bd66756292bf41`.
- Scope: the three canonical selectors; collection completed with 340 nodes.
- Unittest stage: 36 tests completed successfully with no reported skips.
- Pytest: 318 nodes finished; 54 unique nodes reported failures and no skips.
- The pytest process terminated with Windows exit code `3221225477`
  (`0xC0000005`, access violation) while executing
  `scripts/sc/tests/tc_d1_cer/test_s7_cer.py::test_s7_detached_probe_binds_input_target_outcome_and_output`.
- `source_stable` is true. The run is unsuccessful and incomplete; 22 nodes
  did not finish. No Acceptance, VDD, or Quick Dev action was started.
- No JUnit file was produced because the native pytest process terminated
  before session finalization. No synthetic JUnit was created.

All raw collection/test events, traceback dumps, selected node manifest,
process results, stdout/stderr and source bindings are retained in this
directory. C3 remains OPEN and this evidence does not establish Acceptance
readiness.
