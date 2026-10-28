"""Submit actual current-caller worker input; native tools retain evidence ownership."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/sc'))
import host_session
session=ROOT/'logs/package-b-rebuild-20261028/vdd-host-session'
request_id=sys.argv[1];answer=Path(sys.argv[2]).resolve();request=host_session.read(session/request_id/'request.json')
subprocess.run([sys.executable,'-B',str(ROOT/'scripts/sc/host_session.py'),'respond','--session',str(session),'--request-id',request_id,'--request-sha256',host_session.digest(request),'--output-text-file',str(answer)],cwd=ROOT,check=True)
