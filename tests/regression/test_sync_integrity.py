import json
import pytest
import sync
from kb import KB, KBError


def log(content='first', timestamp='2026-01-01T00:00:00Z', role='user', cid='synthetic-chat'):
    return [dict(type='session_meta', payload={'id': cid}),
            dict(type='response_item', timestamp=timestamp, payload=dict(type='message', role=role,
                 content=[dict(type='input_text', text=content)]))]


def save(path, events):
    path.write_bytes(('\n'.join(json.dumps(e) for e in events)+'\n').encode())


@pytest.fixture
def imported(tmp_path):
    kb=KB(tmp_path/'audit.sqlite3')
    path=tmp_path/'rollout.jsonl'
    save(path, log())
    sync.sync_file(kb, path, name='Synthetic', canonical='synthetic')
    yield kb,path
    assert kb.rows('PRAGMA integrity_check')[0]['integrity_check']=='ok'
    assert kb.rows('PRAGMA foreign_key_check')==[]


@pytest.mark.parametrize('field,value', [('timestamp','changed'),('content','changed'),('role','assistant')])
def test_existing_message_mutation_rejected(imported, field, value):
    kb,path=imported
    before=kb.rows('SELECT * FROM sync_state')
    save(path,log(**{field:value}))
    with pytest.raises(KBError): sync.sync_file(kb,path)
    assert kb.rows('SELECT * FROM sync_state')==before


def test_incomplete_tail_does_not_advance(imported):
    kb,path=imported
    before=kb.rows('SELECT * FROM sync_state')
    with path.open('ab') as f: f.write(b'{"type":')
    with pytest.raises(KBError): sync.sync_file(kb,path)
    assert kb.rows('SELECT * FROM sync_state')==before


def test_truncated_and_replay(imported):
    kb,path=imported
    old=path.read_bytes()
    save(path,log()[:1])
    with pytest.raises(KBError): sync.sync_file(kb,path)
    path.write_bytes(old)
    assert sync.sync_file(kb,path)['unchanged']
    assert len(kb.rows('SELECT * FROM messages'))==1


def test_source_id_cannot_escape_archive_root(tmp_path):
    kb=KB(tmp_path/'db'/'test.sqlite3')
    path=tmp_path/'source.jsonl'
    save(path,log(cid='../outside'))
    with pytest.raises(KBError): sync.sync_file(kb,path,name='Synthetic',canonical='synthetic')
    assert not kb.topics()
