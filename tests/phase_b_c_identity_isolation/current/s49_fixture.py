from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import subprocess, tempfile, uuid, xml.etree.ElementTree as ET

TEST_PROJECT='PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj'
TEST_CLASS='PhaseA.Platform.Tests.PhaseB.Repair.S49BoundaryTests'
@dataclass(frozen=True)
class Result:
    name:str; outcome:str; error:str
def run_boundary_case(root:Path, method:str)->Result:
    name=f'{TEST_CLASS}.{method}'
    with tempfile.TemporaryDirectory(prefix=f's49-{uuid.uuid4().hex}-',dir='C:/tmp') as d:
        p=subprocess.run(['dotnet','test',TEST_PROJECT,'--filter',f'FullyQualifiedName={name}','--logger','trx','--results-directory',d],cwd=root,shell=False,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        files=list(Path(d).glob('*.trx'))
        if len(files)!=1: raise RuntimeError(f'S49 harness did not produce one fresh TRX: exit={p.returncode}')
        ns={'t':'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}; doc=ET.parse(files[0]); ids={x.attrib['id'] for x in doc.findall('.//t:UnitTest',ns) if x.attrib.get('name')==name}; rows=[x for x in doc.findall('.//t:UnitTestResult',ns) if x.attrib.get('testId') in ids]
        if len(rows)!=1: raise RuntimeError(f'S49 TRX identity mismatch: {name}')
        return Result(name,rows[0].attrib.get('outcome',''),rows[0].findtext('t:Output/t:ErrorInfo/t:Message',default='',namespaces=ns))
def assert_boundary(result:Result, failure_id:str)->None:
    if result.outcome=='Passed': return
    if failure_id not in result.error: raise RuntimeError(f'S49 case failed before bound assertion: {result.name}')
    raise AssertionError(f'{failure_id}: {result.error}')
