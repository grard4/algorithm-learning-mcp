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
        c.execute('DROP TABLE sync_sources')
        names=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        before={name:[tuple(r) for r in c.execute('SELECT * FROM "'+name+'"')] for name in names}
    upgraded=KB(target)
    with upgraded.connect() as c:
        after={name:[tuple(r) for r in c.execute('SELECT * FROM "'+name+'"')] for name in names}
    assert before==after
    assert source.rows('SELECT count(*) n FROM schema_migrations')[0]['n']==2


def test_core_v1_upgrade_backfills_sync_source_from_cursor_archive(linked,tmp_path):
    source,_,_=linked
    with source.connect() as c:
        c.execute('INSERT INTO sync_state VALUES(?,?,?,?,NULL)',('chat','archive',2,'2026-01-01T00:00:00Z'))
    target=tmp_path/'legacy-v1.sqlite3'
    source.backup(target)
    legacy=KB(target,initialize=False)
    before=legacy.rows('SELECT id,seq,source_line FROM messages ORDER BY id')
    with legacy.connect() as c:
        c.execute('DROP TABLE sync_sources')
        c.execute("DELETE FROM schema_migrations WHERE name='sync-sources-v1'")
    upgraded=KB(target)
    assert upgraded.rows('SELECT id,seq,source_line FROM messages ORDER BY id')==before
    state=upgraded.rows('SELECT conversation_id,source_hash,line_count FROM sync_state')[0]
    mapping=upgraded.rows('SELECT * FROM sync_sources')[0]
    archive=upgraded.rows('SELECT source_path FROM archives WHERE conversation_id=? AND sha256=?',(state['conversation_id'],state['source_hash']))[0]
    from sync_identity import source_key
    assert mapping['source_key']==source_key(archive['source_path'])
    assert mapping['source_hash']==state['source_hash']
    assert mapping['line_count']==state['line_count']
    assert mapping['seq_offset']==0
    assert upgraded.rows('SELECT count(*) n FROM schema_migrations')[0]['n']==2


def test_core_v1_upgrade_refuses_sync_cursor_without_archive_atomically(tmp_path):
    path=tmp_path/'unsafe-core-v1.sqlite3'
    db=KB(path)
    db.register('Synthetic','synthetic','chat','Synthetic')
    with db.connect() as c:
        c.execute('INSERT INTO sync_state VALUES(?,?,?,?,NULL)',('chat','missing-archive',2,'2026-01-01T00:00:00Z'))
        c.execute('DROP TABLE sync_sources')
        c.execute("DELETE FROM schema_migrations WHERE name='sync-sources-v1'")
        before=[tuple(r) for r in c.execute('SELECT name,sha256,applied_at FROM schema_migrations ORDER BY rowid')]
    with pytest.raises(KBError) as caught:
        KB(path)
    assert caught.value.code=='SYNC_MIGRATION_UNSAFE'
    with contextlib.closing(sqlite3.connect(path)) as c:
        assert c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_sources'").fetchall()==[]
        assert [tuple(r) for r in c.execute('SELECT name,sha256,applied_at FROM schema_migrations ORDER BY rowid')]==before
        assert c.execute('SELECT * FROM sync_state').fetchall()==[('chat','missing-archive',2,'2026-01-01T00:00:00Z',None)]
