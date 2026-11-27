"""Repeatable isolated quality gate; never opens the deployed learning database."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dependencies',action='store_true',help='also query the vulnerability service')
    args=parser.parse_args()
    output=ROOT/'.release-audit'/'quality';output.mkdir(parents=True,exist_ok=True)
    commands=[('static',[sys.executable,'-m','ruff','check','--select','E9,F63,F7,F82','.']),
        ('regression',[sys.executable,'-m','pytest','-q','-W','error::ResourceWarning','--cov=.',
            '--cov-report=xml','--junitxml=test-results.xml']),
        ('dependency_consistency',[sys.executable,'-m','pip','check'])]
    if args.dependencies:
        commands.append(('vulnerabilities',[sys.executable,'-m','pip_audit','--progress-spinner','off',
            '--format','json','--output',str(output/'dependencies.json')]))
    results=[]
    with tempfile.TemporaryDirectory(prefix='algorithm-quality-') as temp:
        env={k:v for k,v in os.environ.items() if not k.startswith('ALGORITHM_')}
        env.update(ALGORITHM_KB=str(Path(temp)/'default.sqlite3'),ALGORITHM_PREFERENCES=str(Path(temp)/'missing.md'))
        for name,command in commands:
            run=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
            (output/(name+'.txt')).write_text(run.stdout+'\n'+run.stderr,encoding='utf-8')
            results.append({'check':name,'exit_code':run.returncode})
            print(name+': '+('PASS' if run.returncode==0 else 'FAIL'))
    (output/'results.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8')
    return int(any(x['exit_code'] for x in results))


if __name__=='__main__':raise SystemExit(main())
