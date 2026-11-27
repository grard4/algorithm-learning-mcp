import contextlib
import sqlite3
from pathlib import Path
import pytest
from kb import KB, KBError


def test_backup_never_overwrites_destination_created_after_check(tmp_path,monkeypatch):
    kb=KB(tmp_path/'source.sqlite3')
    target=tmp_path/'destination.sqlite3'
    original=Path.exists
    injected=[]
    def exists(path):
        if path==target and not injected:
            injected.append(True)
            with contextlib.closing(sqlite3.connect(target)) as c,c:
                c.execute('CREATE TABLE marker(value TEXT)')
                c.execute("INSERT INTO marker VALUES('preserve')")
            return False
        return original(path)
    monkeypatch.setattr(Path,'exists',exists)
    with pytest.raises((KBError,FileExistsError)):kb.backup(target)
    with contextlib.closing(sqlite3.connect(target)) as c:
        assert c.execute('SELECT * FROM marker').fetchall()==[('preserve',)]
