from pathlib import Path
import subprocess,tempfile,uuid,xml.etree.ElementTree as ET
TEST_PROJECT='PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj'
TEST_CLASS='PhaseA.Platform.Tests.PhaseB.Repair.S1BoundaryTests'
def run_boundary_case(root:Path,method:str):
    name=f'{TEST_CLASS}.{method}'
    with tempfile.TemporaryDirectory(prefix=f's1-{uuid.uuid4().hex}-',dir='C:/tmp') as d:
        p=subprocess.run(['dotnet','test',TEST_PROJECT,'--filter',f'FullyQualifiedName={name}','--logger','trx','--results-directory',d],cwd=root,shell=False,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        files=list(Path(d).glob('*.trx'))
        if len(files)!=1: raise RuntimeError(f'S1 harness did not produce one fresh TRX: exit={p.returncode}')
        ns={'t':'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'}; doc=ET.parse(files[0]); ids={x.attrib['id'] for x in doc.findall('.//t:UnitTest',ns) if x.attrib.get('name')==name}; rows=[x for x in doc.findall('.//t:UnitTestResult',ns) if x.attrib.get('testId') in ids]
        if len(rows)!=1: raise RuntimeError(f'S1 TRX identity mismatch: {name}')
        return rows[0].attrib.get('outcome',''),rows[0].findtext('t:Output/t:ErrorInfo/t:Message',default='',namespaces=ns)
def assert_boundary(result,failure):
    if result[0]=='Passed': return
    if failure not in result[1]: raise RuntimeError('S1 boundary failed before bound assertion')
    raise AssertionError(f'{failure}: {result[1]}')
