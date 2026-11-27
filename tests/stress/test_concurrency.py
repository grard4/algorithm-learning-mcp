import os
import subprocess
import sys
from pathlib import Path
from kb import KB

ROOT=Path(__file__).resolve().parents[2]


def test_multiprocess_same_request_is_idempotent(tmp_path):
    db=KB(tmp_path/'shared.sqlite3')
    code="from kb import KB; import sys; k=KB(sys.argv[1]); print(k.register('Synthetic','','same-chat','Synthetic'))"
    workers=[subprocess.Popen([sys.executable,'-c',code,str(db.path)],cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE) for _ in range(6)]
    results=[worker.communicate(timeout=45) for worker in workers]
    assert all(worker.returncode==0 for worker in workers),results
    assert len(db.topics())==1
    assert db.rows('SELECT count(*) n FROM updates')[0]['n']==1
    with db.connect() as c:
        assert c.execute('PRAGMA journal_mode').fetchone()[0]=='wal'
        assert c.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert c.execute('PRAGMA busy_timeout').fetchone()[0]==30000


def test_process_death_rolls_back_transaction(tmp_path):
    db=KB(tmp_path/'crash.sqlite3')
    code="from kb import KB; import sys,os; k=KB(sys.argv[1]); c=k.connect().__enter__()" # use a retained context below
    code="from kb import KB; import sys,os; k=KB(sys.argv[1]); cm=k.connect(); c=cm.__enter__(); c.execute('BEGIN IMMEDIATE'); c.execute(\"INSERT INTO topics VALUES('crash','Crash','crash',NULL,'now')\"); os._exit(17)"
    result=subprocess.run([sys.executable,'-c',code,str(db.path)],cwd=ROOT,timeout=30)
    assert result.returncode==17
    assert db.rows("SELECT * FROM topics WHERE id='crash'")==[]
