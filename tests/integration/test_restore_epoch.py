import subprocess
import sys
from pathlib import Path
from kb import KB


def test_cli_restore_rotates_epoch(tmp_path):
    db=KB(tmp_path/'source.sqlite3')
    epoch=db.rows('SELECT epoch FROM r3_meta')[0]['epoch']
    backup=tmp_path/'backup.sqlite3'
    db.backup(backup)
    restored=tmp_path/'restored.sqlite3'
    proc=subprocess.run([sys.executable,'cli.py','restore',str(backup),str(restored)],
        cwd=Path(__file__).resolve().parents[2],capture_output=True,text=True,timeout=30)
    assert proc.returncode==0,proc.stderr
    output=KB(restored,initialize=False)
    assert output.rows('SELECT epoch FROM r3_meta')[0]['epoch']!=epoch
    assert output.rows('PRAGMA foreign_key_check')==[]
    assert output.rows('PRAGMA integrity_check')[0]['integrity_check']=='ok'
