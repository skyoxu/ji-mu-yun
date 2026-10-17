"""ADR-0041: static admission never substitutes for real CER/TRX evidence."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from red_production_entry_guard import validate_red_production_entry


def fixture(root):
    files = {
        'Prod/Prod.csproj': '<Project/>',
        'Prod/Service.cs': 'namespace Product; public class Service { public bool Check() => true; }',
        'Checks/Checks.csproj': '<Project><PropertyGroup><IsTestProject>true</IsTestProject></PropertyGroup><ItemGroup><ProjectReference Include="../Prod/Prod.csproj"/></ItemGroup></Project>',
        'Checks/BoundaryTests.cs': 'using Product; namespace Checks; public class BoundaryTests { [Fact] public void Actual() { var service = new Service(); Assert.True(service.Check()); } }',
        'tests/test_boundary.py': "import subprocess\ndef test_behavior():\n    result = subprocess.run(['dotnet', 'test', 'Checks/Checks.csproj', '--filter', 'FullyQualifiedName=Checks.BoundaryTests.Actual', '--logger', 'trx'], shell=False, capture_output=True)\n    assert result.returncode == 0\n",
    }
    for name, source in files.items():
        p=root/name
        p.parent.mkdir(parents=True,exist_ok=True)
        p.write_text(source,encoding='utf-8')
    b={'plan_id':'PLAN','slices':[{'slice_id':'S1','production_owners':['Prod/Service.cs'],'execution_snapshot_paths':['tests/test_boundary.py','Checks/BoundaryTests.cs']}]}
    d={'stage':'red','plan_id':'PLAN','slice_id':'S1','target_refs':['tests/test_boundary.py'],'fixture_refs':['Checks/BoundaryTests.cs']}
    return b,d


def validate(root,b,d):
    return validate_red_production_entry(workspace=root,bundle=b,slice_id='S1',descriptor=d)


def replace(root,path,old,new):
    p=root/path
    p.write_text(p.read_text(encoding='utf-8').replace(old,new),encoding='utf-8')


def test_accepts_bound_dotnet_without_executing_it(tmp_path):
    b,d=fixture(tmp_path)
    r=validate(tmp_path,b,d)
    assert r['status']=='pass'
    assert r['bindings'][0]['fully_qualified_name']=='Checks.BoundaryTests.Actual'
    assert r['bindings'][0]['production_owner']=='Prod/Service.cs'
    assert r['tests_executed'] is False and r['authorizes']==[]


@pytest.mark.parametrize('path,old,new',[
    ('tests/test_boundary.py',"'dotnet'","'echo'"),
    ('tests/test_boundary.py','shell=False','shell=True'),
    ('tests/test_boundary.py','shell=False, ',''),
    ('tests/test_boundary.py','FullyQualifiedName=','FullyQualifiedName~'),
    ('tests/test_boundary.py','Checks.BoundaryTests.Actual','Checks.BoundaryTests.Other'),
    ('tests/test_boundary.py',"'Checks/Checks.csproj'","'Prod/Prod.csproj'"),
    ('tests/test_boundary.py',"'trx'","'console'"),
    ('tests/test_boundary.py',"['dotnet',","['not-dotnet',"),
    ('Checks/Checks.csproj','<IsTestProject>true</IsTestProject>','<IsTestProject>false</IsTestProject>'),
    ('Checks/Checks.csproj','../Prod/Prod.csproj','Missing.csproj'),
    ('Checks/BoundaryTests.cs','new Service()','new FakeService()'),
    ('Checks/BoundaryTests.cs','namespace Checks;','namespace Wrong;'),
    ('Checks/BoundaryTests.cs','class BoundaryTests','class Wrong'),
    ('Checks/BoundaryTests.cs','[Fact]',''),
    ('Checks/BoundaryTests.cs','new Service()','default(Service)'),
    ('Checks/BoundaryTests.cs','new Service()','null /* new Service() */'),
    ('Checks/BoundaryTests.cs','new Service()','"new Service()"'),
    ('Checks/BoundaryTests.cs','new Service()','null; } } public class Service { public void Fake() { new Service()'),
    ('tests/test_boundary.py','assert result.returncode == 0','assert False'),
    ('Checks/BoundaryTests.cs','Assert.True(service.Check())','Assert.True(false)'),
])
def test_rejects_unbound_or_fabricated_entry(tmp_path,path,old,new):
    b,d=fixture(tmp_path)
    replace(tmp_path,path,old,new)
    with pytest.raises(ValueError):
        validate(tmp_path,b,d)


def test_requires_frozen_csharp_source(tmp_path):
    b,d=fixture(tmp_path)
    b['slices'][0]['execution_snapshot_paths']=['tests/test_boundary.py']
    with pytest.raises(ValueError):
        validate(tmp_path,b,d)


def test_rejects_project_escape(tmp_path):
    b,d=fixture(tmp_path)
    replace(tmp_path,'tests/test_boundary.py','Checks/Checks.csproj','../Checks.csproj')
    with pytest.raises(ValueError):
        validate(tmp_path,b,d)


def test_accepts_static_call_and_subprocess_alias(tmp_path):
    b,d=fixture(tmp_path)
    replace(tmp_path,'Prod/Service.cs','public bool Check()','public static bool Check()')
    replace(tmp_path,'Checks/BoundaryTests.cs','var service = new Service(); Assert.True(service.Check());','Assert.True(Product.Service.Check());')
    replace(tmp_path,'tests/test_boundary.py','import subprocess','from subprocess import run as execute')
    replace(tmp_path,'tests/test_boundary.py','subprocess.run','execute')
    assert validate(tmp_path,b,d)['status']=='pass'


def test_accepts_host_binding(tmp_path):
    b,d=fixture(tmp_path)
    replace(tmp_path,'Prod/Service.cs','namespace Product; public class Service { public bool Check() => true; }','public partial class Program {}')
    replace(tmp_path,'Checks/BoundaryTests.cs','var service = new Service(); Assert.True(service.Check());','using var factory = new WebApplicationFactory<Program>(); using var client = factory.CreateClient(); Assert.NotNull(client);')
    assert validate(tmp_path,b,d)['tests_executed'] is False
