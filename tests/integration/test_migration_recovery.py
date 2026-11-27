import sqlite3
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
    with sqlite3.connect(path) as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[]


def test_unknown_schema_refused_without_changes(tmp_path):
    path=tmp_path/'test.sqlite3'
    with sqlite3.connect(path) as c: c.execute('PRAGMA user_version=999')
    with pytest.raises(KBError): KB(path)
    with sqlite3.connect(path) as c:
        assert c.execute('PRAGMA user_version').fetchone()[0]==999
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()==[]


def test_legacy_schema_drift_refused(tmp_path):
    path=tmp_path/'test.sqlite3'
    with sqlite3.connect(path) as c:
        c.execute('CREATE TABLE topics(id TEXT PRIMARY KEY, name TEXT)')
    with pytest.raises(KBError): KB(path)


def test_migration_checksum_and_repeat_start(tmp_path):
    path=tmp_path/'test.sqlite3'
    db=KB(path)
    assert KB(path).rows('PRAGMA integrity_check')[0]['integrity_check']=='ok'
    with db.connect() as c: c.execute("UPDATE schema_migrations SET sha256='tampered'")
    with pytest.raises(KBError): KB(path)
