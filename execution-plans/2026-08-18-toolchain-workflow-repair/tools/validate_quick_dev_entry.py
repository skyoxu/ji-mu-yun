from __future__ import annotations
import argparse, json, subprocess
from pathlib import Path

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--repository-root',type=Path,required=True); parser.add_argument('--plan-dir',type=Path,required=True); parser.add_argument('--out',type=Path,required=True); args=parser.parse_args()
    root=args.repository_root.resolve(); plan=args.plan_dir.resolve(); round_dir=plan/'repair'/'round-1'; failures=[]
    for name in ('repair-closure.v1.json','plan-validation-receipt.v2.json','quick-dev-entry-receipt.v1.json'):
        if not (round_dir/name).is_file(): failures.append(f'missing:{name}')
    if (round_dir/'repair-closure.v1.json').is_file():
        closure=json.loads((round_dir/'repair-closure.v1.json').read_text(encoding='utf-8'))
        if closure.get('status')!='pass' or closure.get('authorizes')!=[]: failures.append('closure-not-pass')
    authorization = plan / 'implementation-authorization-receipt.successor.v1.json'
    if not authorization.is_file():
        failures.append('authorization-receipt-missing')
    else:
        receipt = json.loads(authorization.read_text(encoding='utf-8'))
        binding = receipt.get('skill_input_receipt')
        if not isinstance(binding, dict) or not isinstance(binding.get('path'), str):
            failures.append('skill-input-binding-missing')
        else:
            skill_input = root / binding['path']
            validation = subprocess.run([
                'python', 'scripts/python/validate_skill_input_consumption.py', str(skill_input),
                '--repository-root', '.', '--contract', '.agents/skills/quick-dev-tdd-adapter/references/skill-input-contract.v1.json',
                '--require-ready',
            ], cwd=root, capture_output=True, text=True)
            if validation.returncode != 0:
                failures.append('skill-input-not-ready')
    route=subprocess.run(['python','.agents/skills/quick-dev-tdd-adapter/tools/route_plan_directory.py','--repository-root','.','--plan-dir',str(plan.relative_to(root)),'--caller','quick-dev-tdd-adapter'],cwd=root,capture_output=True,text=True)
    try: routed=json.loads(route.stdout)
    except json.JSONDecodeError: routed={}
    if routed.get('next_action')!='run-slice' or routed.get('slice_id')!='W0': failures.append('route-not-w0')
    result={'schema_version':'toolchain-workflow-repair.quick-dev-entry-validation.v1','predicate':'quick-dev-entry-ready','status':'pass' if not failures else 'fail','failures':failures,'next_action':'run-slice' if not failures else 'repair','slice_id':'W0' if not failures else None,'authorizes':[],'lifecycle_transition':'none'}
    args.out.parent.mkdir(parents=True,exist_ok=True); args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+'\n',encoding='utf-8',newline='\n'); print(json.dumps(result)); return 0 if not failures else 1
if __name__=='__main__': raise SystemExit(main())
