import importlib
from kb import KB


def test_normalized_import_cannot_escape_archive_directory(tmp_path,monkeypatch):
    server=importlib.import_module('server')
    kb=KB(tmp_path/'db'/'test.sqlite3')
    monkeypatch.setattr(server,'kb',kb)
    kb.register('Synthetic','','../outside','Synthetic')
    result=server.record_conversation_update('../outside',[dict(role='user',content='synthetic',timestamp='2026-11-27T00:00:00Z')],'request')
    assert result['ok'] is False
    assert not kb.rows('SELECT * FROM archives')


def test_normalized_import_rejects_non_text_and_replays(tmp_path,monkeypatch):
    server=importlib.import_module('server')
    kb=KB(tmp_path/'db'/'test.sqlite3')
    monkeypatch.setattr(server,'kb',kb)
    kb.register('Synthetic','','chat','Synthetic')
    invalid=server.record_conversation_update('chat',[dict(role='user',content={'not':'text'},timestamp='2026-11-27T00:00:00Z')],'bad')
    assert invalid['ok'] is False
    assert not kb.rows('SELECT * FROM archives')
    messages=[dict(role='user',content='synthetic',timestamp='2026-11-27T00:00:00Z')]
    first=server.record_conversation_update('chat',messages,'good')
    assert first['ok']
    assert server.record_conversation_update('chat',messages,'good')==first
