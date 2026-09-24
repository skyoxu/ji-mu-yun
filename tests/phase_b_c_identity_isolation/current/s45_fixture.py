from pathlib import Path
import subprocess,tempfile,uuid,xml.etree.ElementTree as ET
def run_boundary_case(root,method):
 n=f'PhaseA.Platform.Tests.PhaseB.Repair.S45BoundaryTests.{method}'
 with tempfile.TemporaryDirectory(prefix='s45-',dir='C:/tmp') as d:
  p=subprocess.run(['dotnet','test','PhaseA.Platform.Tests/PhaseA.Platform.Tests.csproj','--filter',f'FullyQualifiedName={n}','--logger','trx','--results-directory',d],cwd=root,shell=False,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
  f=list(Path(d).glob('*.trx'))
  if len(f)!=1: raise RuntimeError(f'S45 harness did not produce one fresh TRX: exit={p.returncode}')
  ns={'t':'http://microsoft.com/schemas/VisualStudio/TeamTest/2010'};doc=ET.parse(f[0]);ids={x.attrib['id'] for x in doc.findall('.//t:UnitTest',ns) if x.attrib.get('name')==n}; rows=[x for x in doc.findall('.//t:UnitTestResult',ns) if x.attrib.get('testId') in ids];return rows[0].attrib.get('outcome',''),rows[0].findtext('t:Output/t:ErrorInfo/t:Message',default='',namespaces=ns)
