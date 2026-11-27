import subprocess
import sys
import json
import os
import pytest
from pathlib import Path
from kb import KB


@pytest.mark.parametrize('encoding', [None, 'cp1252', 'ascii'])
def test_cli_restore_rotates_epoch(tmp_path, encoding):
    db=KB(tmp_path/'source.sqlite3')
    epoch=db.rows('SELECT epoch FROM r3_meta')[0]['epoch']
    backup=tmp_path/'backup.sqlite3'
    db.backup(backup)
    restored=tmp_path/'恢复.sqlite3'
    env=dict(os.environ)
    if encoding: env['PYTHONIOENCODING']=encoding
    proc=subprocess.run([sys.executable,'cli.py','restore',str(backup),str(restored)],
        cwd=Path(__file__).resolve().parents[2],capture_output=True,timeout=30,env=env)
    assert proc.returncode==0,proc.stderr
    result=json.loads(proc.stdout.decode(encoding or 'utf-8'))
    assert result['restored']==str(restored)
    assert '验证后停止后台进程' in result['activation']
    output=KB(restored,initialize=False)
    assert output.rows('SELECT epoch FROM r3_meta')[0]['epoch']!=epoch
    assert output.rows('PRAGMA foreign_key_check')==[]
    assert output.rows('PRAGMA integrity_check')[0]['integrity_check']=='ok'
