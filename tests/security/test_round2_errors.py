import importlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import pytest
from errors import error_response

@pytest.mark.parametrize('exc,code',[(FileNotFoundError(2,'private-location','private-location'),'SOURCE_UNAVAILABLE'),(PermissionError(13,'private-location'),'PERMISSION_DENIED'),(OSError(5,'private-location'),'STORAGE_UNAVAILABLE'),(sqlite3.OperationalError('private-location'),'DATABASE'),(sqlite3.IntegrityError('private-location'),'CONSTRAINT'),(ValueError('private-location'),'INVALID_INPUT'),(RuntimeError('private-location'),'INTERNAL_ERROR')])
def test_safe_errors_and_diagnostics(exc,code,caplog):
    result=error_response(exc)
    assert not result['ok'] and result['error']['code']==code
    assert 'private-location' not in json.dumps(result)+caplog.text
    assert type(exc).__name__ in caplog.text

def test_tool_storage_failure(tmp_path,monkeypatch,caplog):
    s=importlib.import_module('server')
    def fail(*args,**kwargs):raise PermissionError(13,'private-location')
    monkeypatch.setattr(s.kb,'rows',fail)
    result=s.sync_conversation('synthetic')
    assert result['error']['code']=='PERMISSION_DENIED'
    assert 'private-location' not in json.dumps(result)+caplog.text

@pytest.mark.parametrize('operation',['backup','restore','call'])
def test_cli_error_no_traceback(tmp_path,operation):
    root=Path(__file__).resolve().parents[2]
    missing=tmp_path/'private-location'/'no-file'
    if operation=='backup':
        missing.parent.mkdir()
        missing.write_text('block directory creation',encoding='utf-8')
    args={'backup':[str(missing/'db')],'restore':[str(missing),str(tmp_path/'out.sqlite3')],'call':['list_all_topics','--args-file',str(missing)]}[operation]
    env=dict(os.environ,ALGORITHM_KB=str(tmp_path/'db.sqlite3'))
    p=subprocess.run([sys.executable,str(root/'cli.py'),operation,*args],cwd=root,env=env,capture_output=True,text=True)
    assert p.returncode==1
    assert not json.loads(p.stdout)['ok']
    assert 'private-location' not in p.stdout+p.stderr and 'Traceback' not in p.stderr

def test_startup_storage_error_no_traceback(tmp_path):
    root=Path(__file__).resolve().parents[2]
    blocked=tmp_path/'private-location';blocked.write_text('file',encoding='utf-8')
    env=dict(os.environ,ALGORITHM_KB=str(blocked/'db.sqlite3'))
    p=subprocess.run([sys.executable,str(root/'server.py')],cwd=root,env=env,capture_output=True,text=True)
    assert p.returncode!=0
    assert 'private-location' not in p.stdout+p.stderr and 'Traceback' not in p.stderr

def test_sync_worker_errors_hide_source_path(tmp_path,monkeypatch,caplog):
    import sync
    from kb import KB
    k=KB(tmp_path/'db.sqlite3');k.register('Test','','chat','Test')
    p=tmp_path/'rollout-chat-private-location.jsonl';p.write_bytes(b'')
    monkeypatch.setattr(sync,'sources',lambda home:[p])
    monkeypatch.setattr(sync,'report',lambda kb:None)
    def fail(*a,**kw):raise PermissionError(13,'private-location')
    monkeypatch.setattr(sync,'sync_file',fail)
    result=sync.run(k,tmp_path)
    assert result[0]['error']['code']=='PERMISSION_DENIED'
    assert 'private-location' not in json.dumps(result)+caplog.text
