import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.agents/skills/quick-dev-tdd-adapter/tools'))
from runtime_evidence import current_snapshot
old=json.loads((ROOT/'logs/quick-dev/20260930-plan-q8-r7/implementation-complete.v2.json').read_text(encoding='utf-8'))
terminal=json.loads((ROOT/'logs/quick-dev/20260930-plan-q8-r7/terminal-input.v2.json').read_text(encoding='utf-8'))
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
baseline=terminal['snapshot_manifest']['git_delta']['base_commit']
roots=[{**{k:x[k] for k in ('repository_relative_posix_path','root_kind','inclusion_reason')},'source_commit':baseline} for x in terminal['snapshot_manifest']['roots']]
snapshot=current_snapshot(ROOT,roots,source_commit=baseline,base_commit=head)
out=ROOT/'logs/acceptance/8-24-r2'; out.mkdir(parents=True,exist_ok=True)
(out/'predecessors.v1.json').write_text(json.dumps(old['predecessors'],indent=2)+'\n',encoding='utf-8')
(out/'snapshot-roots.v2.json').write_text(json.dumps(snapshot['roots'],indent=2)+'\n',encoding='utf-8')
print(json.dumps({'head':head,'predecessors':len(old['predecessors']),'roots':len(snapshot['roots'])}))
