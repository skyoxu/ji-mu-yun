import pytest
from s54_fixture import invoke_s54_boundary


def assert_boundary(tmp_path, method, failure_id):
    if invoke_s54_boundary(tmp_path, method):
        return
    print(f"FAILURE_ID:{failure_id}")
    raise AssertionError(f"{failure_id}: real HostedProcessRunner boundary is not enforced")


@pytest.mark.cer_assertion("A-O-12F85445CCD2-OS-WRITE-DENIAL")
def test_o_12f85445ccd2(tmp_path): assert_boundary(tmp_path, "O_12F85445CCD2", "FAILURE-O-12F85445CCD2")
@pytest.mark.cer_assertion("A-O-1D8CB3E8262F-OS-READ-DENIAL")
def test_o_1d8cb3e8262f(tmp_path): assert_boundary(tmp_path, "O_1D8CB3E8262F", "FAILURE-O-1D8CB3E8262F")
@pytest.mark.cer_assertion("A-270713-CHILDREN-TERMINATE")
def test_o_270713f3b6bc(tmp_path): assert_boundary(tmp_path, "O_270713F3B6BC", "FAILURE-O-270713F3B6BC")
@pytest.mark.cer_assertion("A-O-358D470F6E85-OS-STAGING-WRITE-DENIAL")
def test_o_358d470f6e85(tmp_path): assert_boundary(tmp_path, "O_358D470F6E85", "FAILURE-O-358D470F6E85")
@pytest.mark.cer_assertion("A-O-3FA9A1207C61-OS-SECRETS-READ-DENIAL")
def test_o_3fa9a1207c61(tmp_path): assert_boundary(tmp_path, "O_3FA9A1207C61", "FAILURE-O-3FA9A1207C61")
@pytest.mark.cer_assertion("A-O-4178BD27EC32")
def test_o_4178bd27ec32(tmp_path): assert_boundary(tmp_path, "O_4178BD27EC32", "FAILURE-O-4178BD27EC32")
@pytest.mark.cer_assertion("A-O-4834E9163638")
def test_o_4834e9163638(tmp_path): assert_boundary(tmp_path, "O_4834E9163638", "FAILURE-O-4834E9163638")
@pytest.mark.cer_assertion("A-O-4E130E94995A")
def test_o_4e130e94995a(tmp_path): assert_boundary(tmp_path, "O_4E130E94995A", "FAILURE-O-4E130E94995A")
@pytest.mark.cer_assertion("A-O-5CBD9C2F5F8E")
def test_o_5cbd9c2f5f8e(tmp_path): assert_boundary(tmp_path, "O_5CBD9C2F5F8E", "FAILURE-O-5CBD9C2F5F8E")
@pytest.mark.cer_assertion("A-O-B21A2E1BF669")
def test_o_b21a2e1bf669(tmp_path): assert_boundary(tmp_path, "O_B21A2E1BF669", "FAILURE-O-B21A2E1BF669")
@pytest.mark.cer_assertion("A-O-C5E83411E41D")
def test_o_c5e83411e41d(tmp_path): assert_boundary(tmp_path, "O_C5E83411E41D", "FAILURE-O-C5E83411E41D")
@pytest.mark.cer_assertion("A-O-D6F9AC452A48")
def test_o_d6f9ac452a48(tmp_path): assert_boundary(tmp_path, "O_D6F9AC452A48", "FAILURE-O-D6F9AC452A48")
@pytest.mark.cer_assertion("ASSERT-824-ACCOUNT-ROOT-ENUMERATION")
def test_o_824_account_root_enumeration(tmp_path): assert_boundary(tmp_path, "O_824_ACCOUNT_ROOT_ENUMERATION", "FAILURE-O-824-ACCOUNT-ROOT-ENUMERATION")
