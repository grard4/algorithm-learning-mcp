import json
import pytest
import sync
from kb import KB, KBError

CID = '12345678-1234-1234-1234-123456789abc'

def configure(tmp_path, monkeypatch, value):
    (tmp_path/'config').mkdir()
    (tmp_path/'config/discovery_exclusions.json').write_text(json.dumps(value))
    monkeypatch.setattr(sync, 'ROOT', tmp_path)
    monkeypatch.setattr(sync, 'discovery_cutoff', lambda: 0)
    monkeypatch.setattr(sync, 'report', lambda kb: None)
    monkeypatch.setattr(sync, '_scanned', {})

def test_excluded_unregistered_source_is_not_opened(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch, [CID])
    path=tmp_path/f'rollout-{CID}.jsonl'
    monkeypatch.setattr(sync, 'sources', lambda home: [path])
    monkeypatch.setattr(sync, 'sync_file', lambda *a, **kw: pytest.fail('excluded source opened'))
    assert sync.run(KB(tmp_path/'kb.sqlite3'), tmp_path, discover=True)==[{'excluded':CID}]

def test_registered_course_takes_precedence(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch, [CID])
    path=tmp_path/f'rollout-{CID}.jsonl'
    path.write_text(json.dumps({'type':'session_meta','payload':{'id':CID}})+'\n')
    kb=KB(tmp_path/'kb.sqlite3')
    sync.sync_file(kb,path,name='Synthetic',canonical='synthetic')
    monkeypatch.setattr(sync,'sources',lambda home:[path])
    assert sync.run(kb,tmp_path,discover=True)==[{'conversation_id':CID,'unchanged':True}]

def test_invalid_exclusion_is_rejected(tmp_path, monkeypatch):
    configure(tmp_path, monkeypatch, ['../all'])
    with pytest.raises(KBError,match='UUID'):
        sync.discovery_exclusions()

def test_failed_source_has_opaque_identity(tmp_path, monkeypatch):
    configure(tmp_path,monkeypatch,[])
    path=tmp_path/'private-rollout.jsonl';path.write_text('invalid\n')
    monkeypatch.setattr(sync,'sources',lambda home:[path])
    result=sync.run(KB(tmp_path/'kb.sqlite3'),tmp_path,discover=True)[0]
    assert result['ok'] is False and result['source_id']==sync.digest(str(path))
    assert str(path) not in json.dumps(result)
