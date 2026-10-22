"""ADR-0041: static narrowing is bounded and does not import candidate tests."""
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from case_selection import literal_nodes


def select(tmp_path, source, targets=None, required=None):
    (tmp_path/'test_one.py').write_text(source,encoding='utf-8')
    return literal_nodes(tmp_path,targets or ['test_one.py'], required or {'A'})


def test_explicit_ids_and_class_scope(tmp_path):
    source="""raise RuntimeError('must not import')
import pytest
class TestCases:
 @pytest.mark.cer_assertion('A')
 @pytest.mark.parametrize('v', [1, 2], ids=['one', 'two'])
 def test_values(self, v): pass
"""
    nodes, reason=select(tmp_path,source)
    assert nodes==['test_one.py::TestCases::test_values[one]','test_one.py::TestCases::test_values[two]']
    assert reason=='complete-static-case-mapping'
    assert select(tmp_path,source,['test_one.py::TestCases::test_values[one]'])[0]==nodes[:1]
    assert select(tmp_path,source,['test_one.py::TestCases'])[0]==nodes


@pytest.mark.parametrize('tail',[
 "@pytest.mark.parametrize('v', make_values())",
 "@pytest.mark.parametrize('v', [1], ids=make_ids())",
 "@pytest.mark.parametrize('v', [1], indirect=True)",
 "@pytest.mark.parametrize('v', [1,2], ids=['same','same'])",
 "@pytest.mark.parametrize('v', [1], ids=['nonascii-é'])",
])
def test_unsupported_mapping_preserves_declared_selector(tmp_path,tail):
    source="import pytest\n@pytest.mark.cer_assertion('A')\n"+tail+"\ndef test_values(v): pass\n"
    assert select(tmp_path,source)[0] is None


def test_parameter_marks_and_literal_unrelated_cases(tmp_path):
    source="""import pytest
@pytest.mark.parametrize('v', [pytest.param(1,id='one',marks=pytest.mark.cer_assertion('A')), pytest.param(2,id='two',marks=pytest.mark.cer_assertion('A'))])
def test_values(v): pass
@pytest.mark.parametrize('v', [1, 2])
def test_unrelated(v): pass
"""
    assert select(tmp_path,source)[0]==['test_one.py::test_values[one]','test_one.py::test_values[two]']


@pytest.mark.parametrize('source',[
 "import pytest\npytestmark=pytest.mark.cer_assertion('A')\ndef test_one(): pass\n",
 "class TestOne(Base):\n def test_one(self): pass\n",
 "import pytest\n@pytest.mark.cer_assertion(dynamic)\ndef test_one(): pass\n",
 "import pytest\n@pytest.mark.cer_assertion('B')\ndef test_one(): pass\n",
])
def test_incomplete_or_unsupported_never_narrows(tmp_path,source):
    assert select(tmp_path,source)[0] is None


def test_explicit_node_does_not_expand_to_sibling(tmp_path):
    source="""import pytest
@pytest.mark.cer_assertion('A')
def test_a(): pass
@pytest.mark.cer_assertion('B')
def test_b(): pass
"""
    assert select(tmp_path,source,['test_one.py::test_a'],{'A','B'})[0] is None


def test_unrelated_dynamic_row_is_not_assumed_unmarked(tmp_path):
    source="""import pytest
@pytest.mark.cer_assertion('A')
def test_a(): pass
@pytest.mark.parametrize('v', [make_case()])
def test_b(v): pass
"""
    assert select(tmp_path,source)[0] is None
