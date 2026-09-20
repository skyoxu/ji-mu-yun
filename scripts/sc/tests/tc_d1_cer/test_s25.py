"""CER coverage for S1: escaping targets fail closed before use."""
from __future__ import annotations

import pytest

from scripts.toolchain import candidate_content_paths


FAILURE_ID = "ESCAPING_TARGET_ACCEPTED"


@pytest.mark.cer_assertion("A-O-51605D0F7943-ESCAPING-TARGET")
def test_escaping_target_is_rejected_before_use() -> None:
    try:
        candidate_content_paths.classify_path("../outside")
    except ValueError:
        rejected = True
    else:
        rejected = False

    if not rejected:
        print(f"FAILURE_ID:{FAILURE_ID}")
    assert rejected, "escaping target was accepted for classification"
