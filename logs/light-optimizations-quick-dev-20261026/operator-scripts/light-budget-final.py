import json,os,sys
from pathlib import Path
r=Path('/workspace/ji-mu-yun-light-optimizations');sys.path.insert(0,str(r/'scripts'))
from workflow_unit_budget import supervise
label,*argv=sys.argv[1:];directory=r/'logs/light-optimizations-quick-dev-20261026/final-checks'/label;directory.mkdir(parents=True,exist_ok=True)
for name in ('stdout.txt','stderr.txt'):
 if (directory/name).exists():raise SystemExit('Refusing to overwrite output')
env=dict(os.environ,PATH='/tmp/ji-mu-yun-light-qd-venv/bin:'+os.environ['PATH'],TMPDIR=str(r/'logs/light-optimizations-quick-dev-20261026/tmp'),PYTHONDONTWRITEBYTECODE='1')
stdout,stderr=sys.stdout,sys.stderr
with (directory/'stdout.txt').open('w',encoding='utf-8') as out,(directory/'stderr.txt').open('w',encoding='utf-8') as err:
 saved_out,saved_err=os.dup(1),os.dup(2)
 os.dup2(out.fileno(),1);os.dup2(err.fileno(),2)
 sys.stdout,sys.stderr=out,err
 try:code=supervise(argv,cwd=r,directory=directory/'budget',total=1800,idle=600,env=env)
 finally:
  sys.stdout,sys.stderr=stdout,stderr
  os.dup2(saved_out,1);os.dup2(saved_err,2);os.close(saved_out);os.close(saved_err)
print(json.dumps({'label':label,'exit_code':code,'stdout':str((directory/'stdout.txt').relative_to(r)),'tail':(directory/'stdout.txt').read_text()[-700:]}),flush=True)
raise SystemExit(code)
