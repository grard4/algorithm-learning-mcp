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


def test_compressed_truncation_and_valid_frames(tmp_path):
    import zstandard
    raw=('\n'.join(json.dumps(e) for e in log())+'\n').encode()
    path=tmp_path/'source.jsonl.zst'
    compressed=zstandard.ZstdCompressor().compress(raw)
    path.write_bytes(compressed[:-2])
    with pytest.raises(KBError): sync.read_bytes(path)
    path.write_bytes(compressed)
    assert sync.read_bytes(path)==raw
    path.write_bytes(compressed+compressed)
    assert sync.read_bytes(path)==raw+raw


def test_failure_inside_sync_rolls_back_and_retries(imported, monkeypatch):
    kb,path=imported
    save(path, log()+log('second')[1:])
    before=kb.rows('SELECT * FROM sync_state')
    original=kb.mutate
    def fail(operation, request_id, actor, cid, payload, fn):
        def interrupted(c,u):
            fn(c,u)
            raise RuntimeError('simulated interruption before commit')
        return original(operation,request_id,actor,cid,payload,interrupted)
    monkeypatch.setattr(kb,'mutate',fail)
    with pytest.raises(RuntimeError): sync.sync_file(kb,path)
    assert len(kb.rows('SELECT * FROM messages'))==1
    assert kb.rows('SELECT * FROM sync_state')==before
    monkeypatch.setattr(kb,'mutate',original)
    assert sync.sync_file(kb,path)['imported']==1
    assert sync.sync_file(kb,path)['unchanged']
    for archive in kb.rows('SELECT * FROM archives'):
        from pathlib import Path
        assert sync.digest(Path(archive['path']).read_bytes())==archive['sha256']


def test_message_reordering_rejected(imported):
    kb,path=imported
    save(path,log()+log('second')[1:])
    sync.sync_file(kb,path)
    save(path,[log()[0],log('second')[1],log()[1]])
    with pytest.raises(KBError): sync.sync_file(kb,path)


def test_actual_process_death_during_sync_recovers(imported):
    import subprocess,sys
    from pathlib import Path
    kb,path=imported
    save(path,log()+log('second')[1:])
    code='''import sys,os
from kb import KB
import sync
k=KB(sys.argv[1]); original=k.mutate
def crash(operation,request,actor,cid,payload,fn):
    def interrupted(c,u):
        fn(c,u)
        os._exit(17)
    return original(operation,request,actor,cid,payload,interrupted)
k.mutate=crash
sync.sync_file(k,sys.argv[2])
'''
    result=subprocess.run([sys.executable,'-c',code,str(kb.path),str(path)],cwd=Path(__file__).resolve().parents[2],timeout=30)
    assert result.returncode==17
    assert len(kb.rows('SELECT * FROM messages'))==1
    assert sync.sync_file(kb,path)['imported']==1
    assert sync.sync_file(kb,path)['unchanged']


def test_extraction_resumes_after_committed_archive(imported,monkeypatch):
    kb,path=imported
    save(path,log()+log('复杂度与正确性：'+'synthetic explanation '*30,role='assistant')[1:])
    original=sync.finish_extraction
    def fail(*args):raise RuntimeError('interrupted after archive commit')
    monkeypatch.setattr(sync,'finish_extraction',fail)
    with pytest.raises(RuntimeError):sync.sync_file(kb,path)
    assert len(kb.rows('SELECT * FROM messages'))==2
    assert not kb.rows('SELECT * FROM knowledge_items')
    monkeypatch.setattr(sync,'finish_extraction',original)
    assert sync.sync_file(kb,path)['unchanged']
    assert len(kb.rows('SELECT * FROM knowledge_items'))==1
    sync.sync_file(kb,path)
    assert len(kb.rows('SELECT * FROM knowledge_items'))==1
