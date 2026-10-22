"""ADR-0041: read-only retained-plan audit, never historical republication."""
from pathlib import Path
import hashlib
import json
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'.agents/skills/vdd-execution-plan/scripts'))
import semantic_compiler_authority
import semantic_compiler as sc
from semantic_chain_audit import audit_bundle
from execution_preflight import inspect_candidate

paths = [
 'execution-plans/2026-08-05-toolchain-core-skill-replay-portability-and-evaluation-seed/repair/round-7/recompilation-4/cer-repair-1/current-plan',
 'execution-plans/2026-08-06-skill-authoring-standard/current-plan',
 'execution-plans/2026-08-24-phase-b-c-identity-isolation-workspace-recovery',
]
results = []
for raw in paths:
 path = ROOT/raw/'semantic-plan-bundle.v1.json'
 before = path.read_bytes()
 bundle = json.loads(before)
 contexts = {c['slice_id']: c for c in bundle['agent_contexts']}
 hints = []
 # This projection is not a reproduction of historical V3 worker responses.
 for s in bundle['slices']:
  c = contexts[s['slice_id']]
  for aid in s['acceptance_ids']:
   a = next(a for a in bundle['acceptances'] if a['acceptance_id'] == aid)
   hints.append({**s, 'obligation_ids': a['obligation_ids'],
                 'validation_commands': c['validation_commands'], 'forbidden_paths': c['forbidden_paths']})
 result = inspect_candidate(sc, ROOT, bundle['obligations'], bundle['acceptances'],
                            bundle['failure_intents'], hints, profile=bundle['profile'])
 results.append({'path': raw, 'sha256': hashlib.sha256(before).hexdigest(),
                 'obligations': len(bundle['obligations']), 'slices': len(bundle['slices']),
                 'structural_validation': sc.validate_semantic_bundle(bundle),
                 'chain_audit': audit_bundle(bundle)['valid'],
                 'projected_execution': result, 'authorizes': []})
 assert path.read_bytes() == before
(ROOT/'logs/vdd-stability-20261020/historical-plan-check.json').write_text(
 json.dumps(results, indent=2, ensure_ascii=True)+'\n', encoding='utf-8')
for r in results:
 print(r['path'], 'structural:', r['structural_validation'][0], 'chain:', r['chain_audit'],
       'projected findings:', len(r['projected_execution']['findings']),
       'consumer warnings:', len(r['projected_execution']['consumer_warnings']))
