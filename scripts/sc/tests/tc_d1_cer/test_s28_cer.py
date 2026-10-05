"""CER selectors for S28 replay-matrix identity behavior."""
from __future__ import annotations

import pytest

from test_s28 import (
    test_duplicate_effective_evidence_identity_rejects_aggregate_with_both_cases as _duplicate_identity,
    test_reused_effective_identity_is_not_silently_deduplicated as _reused_identity,
)
from test_s42 import (
    test_duplicate_matrix_input_rejects_six_case_aggregate as _duplicate_matrix_input,
)
from test_s13 import (
    test_unverifiable_identity_and_execution_facts_reject_success as _identity_execution_facts,
)


@pytest.mark.cer_assertion("A-7051147536AB-1")
def test_s28_cer_duplicate_identity_rejection() -> None:
    _duplicate_identity()


@pytest.mark.cer_assertion("SM2-EFFECTIVE-IDENTITY-REUSE")
def test_s28_cer_reused_identity_rejection() -> None:
    _reused_identity()


@pytest.mark.cer_assertion("A-7817-distinct-inputs")
def test_s28_cer_duplicate_matrix_input_rejection() -> None:
    _duplicate_matrix_input()


@pytest.mark.cer_assertion("assert-identity-execution-facts-gate")
def test_s28_cer_identity_execution_facts_control() -> None:
    _identity_execution_facts()
