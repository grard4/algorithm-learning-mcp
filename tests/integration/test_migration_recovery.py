import sqlite3
import contextlib
from pathlib import Path
import pytest
import kb as module
import notifications
from kb import KB, KBError


def test_initialization_failure_is_atomic(tmp_path, monkeypatch):
    path=tmp_path/'test.sqlite3'
    def fail(c): raise RuntimeError('injected late migration failure')
    monkeypatch.setattr(notifications,'install_transaction',fail)
    with pytest.raises(RuntimeError): KB(path)
    with contextlib.closing(sqlite3.connect(path)) as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[]


def test_unknown_schema_refused_without_changes(tmp_path):
    path=tmp_path/'test.sqlite3'
    with contextlib.closing(sqlite3.connect(path)) as c, c: c.execute('PRAGMA user_version=999')
    with pytest.raises(KBError): KB(path)
    with contextlib.closing(sqlite3.connect(path)) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==999
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[]


def test_legacy_schema_drift_refused(tmp_path):
    path=tmp_path/'test.sqlite3'
    with contextlib.closing(sqlite3.connect(path)) as c, c:
        c.execute('CREATE TABLE topics(id TEXT PRIMARY KEY, name TEXT)')
    with pytest.raises(KBError): KB(path)


def test_migration_checksum_and_repeat_start(tmp_path):
    path=tmp_path/'test.sqlite3'
    db=KB(path)
    assert KB(path).rows('PRAGMA integrity_check')[0]['integrity_check']=='ok'
    with db.connect() as c: c.execute("UPDATE schema_migrations SET sha256='tampered'")
    with pytest.raises(KBError): KB(path)


def test_populated_legacy_copy_preserves_all_existing_rows(linked,tmp_path):
    source,_,_=linked
    target=tmp_path/'legacy-copy.sqlite3'
    source.backup(target)
    legacy=KB(target,initialize=False)
    with legacy.connect() as c:
        c.execute('DROP TABLE schema_migrations')
        names=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before={name:[tuple(r) for r in c.execute('SELECT * FROM "'+name+'"')] for name in names}
    upgraded=KB(target)
    with upgraded.connect() as c:
        after={name:[tuple(r) for r in c.execute('SELECT * FROM "'+name+'"')] for name in names}
    assert before==after
    assert source.rows('SELECT count(*) n FROM schema_migrations')[0]['n']==1
