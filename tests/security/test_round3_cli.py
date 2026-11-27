import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('case,code',[
    ('success',None),('business','NOT_FOUND'),('unknown','INVALID_INPUT'),
    ('missing','SOURCE_UNAVAILABLE'),('json','INVALID_INPUT'),('arguments','INVALID_INPUT'),
    ('database','STORAGE_UNAVAILABLE'),('schema','UNKNOWN_SCHEMA_VERSION'),
    ('unexpected','INTERNAL_ERROR'),('plain_success',None)])
def test_cli_status(tmp_path,case,code):
    env=dict(os.environ,ALGORITHM_KB=str(tmp_path/'cli.sqlite3'))
    args=['call','list_all_topics']
    payload={}
    if case=='business':args=['call','get_topic_context'];payload={'topic_id':'absent'}
    if case=='unknown':args=['call','absent']
    path=tmp_path/'args.json';path.write_text(json.dumps(payload),encoding='utf-8')
    if case=='missing':path=tmp_path/'missing.json'
    if case=='json':path.write_text('{',encoding='utf-8')
    args+=['--args-file',str(path)]
    if case=='arguments':args=['call']
    if case=='database':
        block=tmp_path/'block';block.write_text('file',encoding='utf-8')
        env['ALGORITHM_KB']=str(block/'db.sqlite3')
    if case=='schema':
        import sqlite3
        import contextlib
        with contextlib.closing(sqlite3.connect(env['ALGORITHM_KB'])) as db:
            db.execute('PRAGMA user_version=99')
    command=[sys.executable,str(ROOT/'cli.py'),*args]
    if case in ('unexpected','plain_success'):
        # Real CLI entry point in a subprocess; inject only the tool result/failure.
        body="raise RuntimeError('private')" if case=='unexpected' else "return {'legacy': True}"
        script="import server,sys,runpy\ndef stub():\n "+body+"\nserver.list_all_topics=stub\nsys.argv=['cli.py','call','list_all_topics']\nrunpy.run_path('cli.py',run_name='__main__')"
        command=[sys.executable,'-c',script]
    p=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,text=True)
    result=json.loads(p.stdout)
    assert p.returncode==(1 if code else 0)
    if code:assert result['error']['code']==code
    else:assert result.get('ok',True) is True
