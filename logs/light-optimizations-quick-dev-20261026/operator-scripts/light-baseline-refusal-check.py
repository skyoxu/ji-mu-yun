import hashlib,json,sys
from pathlib import Path
r=Path('/workspace/ji-mu-yun-light-optimizations');sys.path.insert(0,str(r));sys.path.insert(0,str(r/'scripts'))
from scripts.vdd import compile_plan as cli
from execution_preflight import inspect_admission
from scripts.toolchain.knowledge_query import adapter
req='execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/assembled-requirements.md'
a=inspect_admission(cli.semantic_compiler,r,r/req,profile='self-hosted')
record='logs/light-optimizations-quick-dev-20261026/read-only-refusal-query-record.md';assert not (r/record).exists()
reason=None
try:
 adapter.prepare_consumption({'stage':'vdd-repair','operation':'repair','task_id':'legacy-fixture-refusal-diagnostic','inputs':[req],'scope':[req],'query':'current source callers tests contracts '+req,'record_path':record},r)
except ValueError as error:reason=str(error)
d={'authorizes':[],'not_completion':True,'source':req,'source_sha256':hashlib.sha256((r/req).read_bytes()).hexdigest(),'adapter_sha256':hashlib.sha256(Path(adapter.__file__).read_bytes()).hexdigest(),'actual_admission_result':a,'actual_consumption_exception':reason,'query_record_exists':(r/record).exists()}
p=r/'logs/light-optimizations-quick-dev-20261026/current-baseline-refusal-diagnostic.v1.json';p.write_text(json.dumps(d,indent=2)+'\n')
assert a['status']!='blocked' and reason=='consumption_reference_denied' and not (r/record).exists()
print('Current admission is pending; actual unchanged consumer rejects the historical reference before query-record creation: '+reason)
