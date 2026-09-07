# Case evidence contract: CER phase 1

Decision: ADR-0041, Case Evidence Capability (2026-09-07).
Scope: CER-R1--R3 in the [upstream requirements](../../../../docs/2026-09-07-vdd-quick-dev-case-evidence-and-regression-routing-requirements.md).

## Authoring and supported execution

Use the current `scripts/quick_dev/run.py` entry. Its descriptor materializer adds
`case_contract` to `quick-dev.stage-descriptor.v2`; that capability is included
in the frozen selector identity. The implementation keeps the existing
receipt, observation and runtime-edge artifacts; there is no second scheduler.

Use `python -m pytest <frozen targets>` with normal pytest capture enabled.
The executor invokes the same Python interpreter and arguments through the
repository-owned `pytest_case_collector.py`, pins rootdir to the descriptor cwd
and disables pytest's cache writer. The actual argv is recorded separately from
the semantic argv. Other formats, custom root overrides, parallel execution and
retries have no admissible adapter in this version. Do not disable capture for
RED: a failure ID must be captured from that case's call, not global stdout.

Bind each assertion explicitly in the test source:

```python
import pytest

@pytest.mark.cer_assertion("ASSERT-DUPLICATE")
@pytest.mark.parametrize("key", ["one", "two"])
def test_duplicate(key):
    ledger = make_ledger()
    ledger.claim(key)
    actual = ledger.claim(key)
    if actual != "duplicate":
        print("FAILURE_ID:DUPLICATE-ACTIVE")
    assert actual == "duplicate"
```

The marker is mapping metadata, not evidence. The owned collector resolves it
into individual node IDs, including parameter IDs, before `-k`/`-m` deselection.
Every resolved case is required. Multiple assertion markers on one test are
allowed only when that test actually checks those assertions. One assertion
may mark several tests. Do not use module-wide markers to claim unrelated tests.
Existing semantic/oracle checks still own the validity of this mapping.

A descriptor can instead freeze explicit `case_ids` with `marker: null`.
These are node IDs relative to descriptor cwd, such as
`tests/test_ledger.py::test_duplicate[one]`. No missing case is replaced by a
case count or by another test from the same file. Freeze the complete intended
case set; changing it requires new RED evidence.

## Embedded schemas

`case_contract` has exactly these fields:

- `schema`: `quick-dev.case-contract.v1`.
- `collector_sha256`: digest of the owned collector code.
- `bindings`: one row for every `(acceptance_id, assertion_id)` in the descriptor.
  Each row contains `acceptance_id`, `assertion_id`, `marker`, `case_ids`, and
  `expected_failure_ids`. Use either an assertion-ID marker with empty case_ids,
  or explicit node IDs with a null marker. Expected failure IDs are projected
  from the Acceptance's expected-red failure intents; the stage pipeline checks
  this projection against the semantic plan before execution.

The receipt embeds `case_report` (`quick-dev.pytest-case-report.v1`),
`case_report_sha256`, `case_report_error`, and `executed_argv`. The report contains
run_id, stage, descriptor_sha256, a fresh nonce, complete, exit_code, collected,
selected, events and errors. Each event records node_id, phase, outcome, xfail,
assertion_failure and scoped failure_ids. The nonce is checked against the
executor-owned request before the report enters the immutable receipt.

The temporary report is created once outside the task's write set. The parent
accepts it only after the current child returns with matching identity and exit
code. A timeout or malformed/missing report never produces case proof. Repeated
collection IDs or repeated `(node_id, phase)` events are ambiguous and rejected;
this version does not stitch attempts together.

## Admission and closure

| Stage or condition | Admission |
| --- | --- |
| RED | Every required case has successful setup/teardown and a failed AssertionError call with its expected failure IDs captured from that call; existing stage-level failure identity checks also pass. |
| GREEN / REFACTOR | Every required case passes setup/call/teardown; the resolved mapping exactly matches RED. Existing selector, target, fixture, write-set and Q6 regression checks still apply. |
| Terminal | Every required case passes under its own frozen terminal descriptor; Q8 checks every required assertion. |
| Collected but deselected, skipped or not executed | No proof. |
| Setup/teardown error, xfail/xpass, timeout | No proof. |
| Old/missing/truncated report or ambiguous repeated attempt | No proof. |
| Extra unmapped case | Recorded; cannot support an unrelated assertion. |

The judge records a specific `case_evidence_error` (for example
`case-missing-or-deselected`, `case-skipped`, `case-unexpected-red`,
`assertion-binding-gap`, `stale-case-evidence`, `case-set-changed-since-red`).
Existing environment, timeout and integrity classifications retain priority.
No dependent runtime edges are emitted when the stage predicate is false.

Q4 re-reads RED case proof before implementation handoff. Q7 and Q8 recompute
case admission from the receipt, check every assertion edge and rehash every
mapped target file. An edge's case_ids and case_report_sha256 must match the
actual report. Q8 checks all assertions, not only the first edge per Acceptance.

## Compatibility and delivery boundary

Historical stage-only descriptors/receipts remain readable as history and keep
their original hashes. They are not upgraded or rewritten. Current execution
requires the explicit capability and current collector digest; current Q4/Q7/Q8
cannot promote old stage-only evidence. Existing tests must declare a mapping
before they can support new completion evidence.

This phase does not implement present/missing/unverifiable disposition,
regression-only completion or Deferred rules (CER-R4--R6). The existing Q6 extra
regression gate remains an additional guard, not a source of assertion proof.
Quick Dev still publishes only implementation-complete, never acceptance-passed.
No CH456 live re-acceptance or new approval layer is required by this increment.
