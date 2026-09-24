import pytest

from s21_fixture import invoke_s21_boundary


def assert_boundary(tmp_path, case, failure_id):
    observation = invoke_s21_boundary(tmp_path, case, failure_id)
    if observation["outcome"] == "Passed" and observation["satisfied"]:
        return
    if observation["outcome"] != "Failed":
        raise RuntimeError(f"S21 boundary was not executable: {observation['outcome']!r}")
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: {case} did not prove its declared behavior")


@pytest.mark.cer_assertion("A-SM-W06-SECRET-EXCLUSION")
def test_o_0da4d1a674fc(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_0DA4D1A674FC", "FAILURE-O-0DA4D1A674FC")


@pytest.mark.cer_assertion("A-SM-W06-TICKET-EXCLUSION")
def test_o_254a534b34dc(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_254A534B34DC", "FAILURE-O-254A534B34DC")


@pytest.mark.cer_assertion("A-SM-W06-GDD-INCLUSION")
def test_o_256764d63b41(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_256764D63B41", "FAILURE-O-256764D63B41")


@pytest.mark.cer_assertion("A-SM-W06-MODULE-INCLUSION")
def test_o_333bfbbdd4e6(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_333BFBBDD4E6", "FAILURE-O-333BFBBDD4E6")


@pytest.mark.cer_assertion("A-O-428F1AED1718-1")
def test_o_428f1aed1718(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_428F1AED1718", "FAILURE-O-428F1AED1718")


@pytest.mark.cer_assertion("A-O-54456853027B-1")
def test_o_54456853027b(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_54456853027B", "FAILURE-O-54456853027B")


@pytest.mark.cer_assertion("A-O-5743-1")
def test_o_5743edd3b96d(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_5743EDD3B96D", "FAILURE-O-5743EDD3B96D")


@pytest.mark.cer_assertion("A-O-6927E3DB2340-1")
def test_o_6927e3db2340(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_6927E3DB2340", "FAILURE-O-6927E3DB2340")


@pytest.mark.cer_assertion("A-O-6F2FD7753C43-BINDING")
@pytest.mark.cer_assertion("A-O-6F2FD7753C43-IMMUTABLE")
def test_o_6f2fd7753c43(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_6F2FD7753C43", "FAILURE-O-6F2FD7753C43")


@pytest.mark.cer_assertion("A-O-7A7ADBD789E8-1")
def test_o_7a7adbd789e8(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_7A7ADBD789E8", "FAILURE-O-7A7ADBD789E8")


@pytest.mark.cer_assertion("RETENTION_EXPIRY_AUDIT")
def test_o_866209dc052d(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_866209DC052D", "FAILURE-O-866209DC052D")


@pytest.mark.cer_assertion("A-O-90F61-1")
def test_o_90f61cb8c839(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_90F61CB8C839", "FAILURE-O-90F61CB8C839")


@pytest.mark.cer_assertion("RETENTION_CLEANUP_AUDIT")
def test_o_9e1b4d8de8e7(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_9E1B4D8DE8E7", "FAILURE-O-9E1B4D8DE8E7")


@pytest.mark.cer_assertion("RETENTION_ACTIVE_RESTORE_INPUTS_PRESERVED")
def test_o_a59bcc9699ea(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_A59BCC9699EA", "FAILURE-O-A59BCC9699EA")


@pytest.mark.cer_assertion("RETENTION_PIN_30_DAY_PROFILE")
def test_o_abfd538c2712(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_ABFD538C2712", "FAILURE-O-ABFD538C2712")


@pytest.mark.cer_assertion("A-O-CC9B0-1")
def test_o_cc9b0a135a23(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_CC9B0A135A23", "FAILURE-O-CC9B0A135A23")


@pytest.mark.cer_assertion("A-ODAE26C389431-FIRST-BYTES")
def test_o_dae26c389431(tmp_path):
    assert_boundary(tmp_path, "PhaseA.Platform.Tests.PhaseB.Repair.S21BoundaryTests.O_DAE26C389431", "FAILURE-O-DAE26C389431")
