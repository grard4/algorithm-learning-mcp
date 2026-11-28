"""Runs native filesystem tests on each CI OS; simulations are named separately."""
import json
import os
import time
from types import SimpleNamespace

import pytest
import sync
from kb import KB


def setup(tmp_path, monkeypatch):
    monkeypatch.setattr(sync, 'ROOT', tmp_path)
    monkeypatch.setattr(sync, '_scanned', {})
    monkeypatch.setattr(sync, 'report', lambda kb: None)
    home = tmp_path/'home'
    (home/'sessions').mkdir(parents=True)
    return KB(tmp_path/'db.sqlite3'), home


def log(home, cid):
    path = home/'sessions'/('rollout-' + cid + '.jsonl')
    path.write_text(json.dumps({'type': 'session_meta', 'payload': {'id': cid}}) + '\n')
    return path


def test_native_old_metadata_changes_new_file_and_restart(tmp_path, monkeypatch):
    kb, home = setup(tmp_path, monkeypatch)
    old = log(home, 'old')
    called = []
    monkeypatch.setattr(sync, 'sync_file', lambda kb, p, **kw: called.append(p.name) or {})
    sync.run(kb, home, discover=True)
    assert called == []
    time.sleep(0.02)
    old.chmod(old.stat().st_mode | 0o200)
    os.utime(old, None)
    sync.run(kb, home, discover=True)
    assert called == [], 'old metadata change must not admit historical chat'
    new = log(home, 'new')
    sync.run(kb, home, discover=True)
    assert called == [new.name]
    sync.run(kb, home, discover=True)
    assert called == [new.name], 'unchanged scan should be cached'
    monkeypatch.setattr(sync, '_scanned', {})
    sync.run(kb, home, discover=True)
    assert called == [new.name, new.name], 'persistent boundary must survive worker restart'


def test_simulated_no_birthtime_old_rename_and_uncertain_identity(tmp_path, monkeypatch):
    from discovery import Boundary
    home = tmp_path/'home'
    home.mkdir()
    old = home/'old'
    old.write_text('old')
    boundary = Boundary(tmp_path/'config', home, [old], 0)
    old.rename(home/'renamed')
    assert not boundary.allows(home/'renamed', SimpleNamespace(st_dev=old.parent.stat().st_dev,
        st_ino=(home/'renamed').stat().st_ino))
    new = home/'new'
    new.write_text('new')
    s = new.stat()
    assert boundary.allows(new, SimpleNamespace(st_dev=s.st_dev, st_ino=s.st_ino))
    assert not boundary.allows(new, SimpleNamespace(st_dev=s.st_dev, st_ino=0))
    assert not boundary.allows(new, SimpleNamespace(st_dev=s.st_dev, st_ino=s.st_ino, st_birthtime=float('nan')))


def test_simulated_birthtime_rejects_old_or_future(tmp_path):
    from discovery import Boundary
    home = tmp_path/'home'
    home.mkdir()
    b = Boundary(tmp_path/'config', home, [], 0)
    p = home/'new'
    p.write_text('new')
    s = p.stat()
    for birth in (0, -1, float('inf'), time.time() + 1000):
        assert not b.allows(p, SimpleNamespace(st_dev=s.st_dev, st_ino=s.st_ino, st_birthtime=birth))


def test_known_file_does_not_need_creation_time(tmp_path, monkeypatch):
    kb, home = setup(tmp_path, monkeypatch)
    p = log(home, 'known')
    sync.sync_file(kb, p, name='Synthetic')
    assert sync.run(kb, home, discover=True)[0]['unchanged']


def test_simulated_posix_ctime_change_does_not_discover_old(tmp_path, monkeypatch):
    kb, home = setup(tmp_path, monkeypatch)
    p = log(home, 'old')
    calls = []
    monkeypatch.setattr(sync, 'sync_file', lambda *args, **kw: calls.append(1) or {})
    sync.run(kb, home, discover=True)

    class MetadataChanged:
        name = p.name

        def __str__(self):
            return str(p)

        def resolve(self):
            return p.resolve()

        def is_symlink(self):
            return False

        def stat(self):
            s = p.stat()
            return SimpleNamespace(st_ctime=time.time() + 1, st_size=s.st_size,
                st_mtime_ns=s.st_mtime_ns, st_dev=s.st_dev, st_ino=s.st_ino)

    monkeypatch.setattr(sync, 'sources', lambda home: [MetadataChanged()])
    sync.run(kb, home, discover=True)
    assert calls == []


def test_corrupt_snapshot_fails_closed(tmp_path):
    from discovery import Boundary
    home = tmp_path/'home'
    home.mkdir()
    b = Boundary(tmp_path/'config', home, [], 0)
    b.path.write_text('{broken')
    with pytest.raises(Exception) as exc:
        Boundary(tmp_path/'config', home, [], 0)
    assert getattr(exc.value, 'code', None) == 'INVALID_DISCOVERY_BOUNDARY'
