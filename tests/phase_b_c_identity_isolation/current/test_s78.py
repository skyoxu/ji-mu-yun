from pathlib import Path

import pytest

from s78_fixture import assert_boundary_passes, run_boundary_case


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _verify(method_name: str, failure_id: str) -> None:
    result = run_boundary_case(REPOSITORY_ROOT, method_name)
    assert_boundary_passes(result, f"S78-OBSERVATION {method_name} snapshot-boundary-verified", failure_id)


@pytest.mark.cer_assertion("A-O005AF027AF20-COMPATIBILITY")
def test_o_005af027af20() -> None:
    _verify("O_005AF027AF20", "FAILURE-O-005AF027AF20")


@pytest.mark.cer_assertion("A-O0B827B3F1DF8-KEYREF")
def test_o_0b827b3f1df8() -> None:
    _verify("O_0B827B3F1DF8", "FAILURE-O-0B827B3F1DF8")


@pytest.mark.cer_assertion("A-O1A6001B8457D-PROJECTID")
def test_o_1a6001b8457d() -> None:
    _verify("O_1A6001B8457D", "FAILURE-O-1A6001B8457D")


@pytest.mark.cer_assertion("A-O-39F52FDEF1AA-1")
def test_o_39f52fdef1aa() -> None:
    _verify("O_39F52FDEF1AA", "FAILURE-O-39F52FDEF1AA")


@pytest.mark.cer_assertion("A-48F7894B3810-KEY-REFERENCE")
def test_o_48f7894b3810() -> None:
    _verify("O_48F7894B3810", "FAILURE-O-48F7894B3810")


@pytest.mark.cer_assertion("A-O-4B55B33561ED-1")
def test_o_4b55b33561ed() -> None:
    _verify("O_4B55B33561ED", "FAILURE-O-4B55B33561ED")


@pytest.mark.cer_assertion("A-O637-RECOVERY-REBUILD")
def test_o_637b22fbd097() -> None:
    _verify("O_637B22FBD097", "FAILURE-O-637B22FBD097")


@pytest.mark.cer_assertion("A-O712-CONTENT-HASHES")
def test_o_71211d09ed69() -> None:
    _verify("O_71211D09ED69", "FAILURE-O-71211D09ED69")


@pytest.mark.cer_assertion("A-O77-STABLE-SNAPSHOT-ID")
def test_o_77c69533e116() -> None:
    _verify("O_77C69533E116", "FAILURE-O-77C69533E116")


@pytest.mark.cer_assertion("A-O-9F0B8CFD82B0")
def test_o_9f0b8cfd82b0() -> None:
    _verify("O_9F0B8CFD82B0", "FAILURE-O-9F0B8CFD82B0")


@pytest.mark.cer_assertion("A-O-A0B263A78B53")
def test_o_a0b263a78b53() -> None:
    _verify("O_A0B263A78B53", "FAILURE-O-A0B263A78B53")


@pytest.mark.cer_assertion("A-O-A1E96696878A-EXCLUSIONS")
def test_o_a1e96696878a() -> None:
    _verify("O_A1E96696878A", "FAILURE-O-A1E96696878A")


@pytest.mark.cer_assertion("A-O-BD6AC3F538D6-CREATOR")
def test_o_bd6ac3f538d6() -> None:
    _verify("O_BD6AC3F538D6", "FAILURE-O-BD6AC3F538D6")


@pytest.mark.cer_assertion("A-O-C099736647B3-RETENTION")
def test_o_c099736647b3() -> None:
    _verify("O_C099736647B3", "FAILURE-O-C099736647B3")


@pytest.mark.cer_assertion("A-O-CA969AA27571-CREATION-ACTION")
def test_o_ca969aa27571() -> None:
    _verify("O_CA969AA27571", "FAILURE-O-CA969AA27571")


@pytest.mark.cer_assertion("A-CC8E549073FD-1")
def test_o_cc8e549073fd() -> None:
    _verify("O_CC8E549073FD", "FAILURE-O-CC8E549073FD")


@pytest.mark.cer_assertion("A-CF08C5874978-1")
def test_o_cf08c5874978() -> None:
    _verify("O_CF08C5874978", "FAILURE-O-CF08C5874978")


@pytest.mark.cer_assertion("A-CF9A089A1346-1")
def test_o_cf9a089a1346() -> None:
    _verify("O_CF9A089A1346", "FAILURE-O-CF9A089A1346")


@pytest.mark.cer_assertion("A-O-D61408107A00")
def test_o_d61408107a00() -> None:
    _verify("O_D61408107A00", "FAILURE-O-D61408107A00")


@pytest.mark.cer_assertion("A-DAF232D67D56-1")
def test_o_daf232d67d56() -> None:
    _verify("O_DAF232D67D56", "FAILURE-O-DAF232D67D56")


@pytest.mark.cer_assertion("A-DB654A6BD822")
def test_o_db654a6bd822() -> None:
    _verify("O_DB654A6BD822", "FAILURE-O-DB654A6BD822")


@pytest.mark.cer_assertion("A-O-DEFE8E5A41DF")
def test_o_defe8e5a41df() -> None:
    _verify("O_DEFE8E5A41DF", "FAILURE-O-DEFE8E5A41DF")


@pytest.mark.cer_assertion("A-O-EBA99C7FA89E-1")
def test_o_eba99c7fa89e() -> None:
    _verify("O_EBA99C7FA89E", "FAILURE-O-EBA99C7FA89E")


@pytest.mark.cer_assertion("A-ED827B133807")
def test_o_ed827b133807() -> None:
    _verify("O_ED827B133807", "FAILURE-O-ED827B133807")


@pytest.mark.cer_assertion("A-EF1F883CB07E")
def test_o_ef1f883cb07e() -> None:
    _verify("O_EF1F883CB07E", "FAILURE-O-EF1F883CB07E")


@pytest.mark.cer_assertion("A-EF2EB8ED143C")
def test_o_ef2eb8ed143c() -> None:
    _verify("O_EF2EB8ED143C", "FAILURE-O-EF2EB8ED143C")


@pytest.mark.cer_assertion("ASSERT-824-SNAPSHOT-PLAN-CONTENT")
def test_o_824_snapshot_plan_content() -> None:
    _verify("O_824_SNAPSHOT_PLAN_CONTENT", "FAILURE-O-824-SNAPSHOT-PLAN-CONTENT")


@pytest.mark.cer_assertion("ASSERT-824-SNAPSHOT-APPROVED-ASSETS")
def test_o_824_snapshot_approved_assets() -> None:
    _verify("O_824_SNAPSHOT_APPROVED_ASSETS", "FAILURE-O-824-SNAPSHOT-APPROVED-ASSETS")
