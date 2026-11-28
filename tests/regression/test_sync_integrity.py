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


def test_unchanged_sync_checks_archive_corruption(imported):
    from pathlib import Path
    kb,path=imported
    archive=Path(kb.rows('SELECT path FROM archives')[0]['path'])
    archive.write_bytes(b'corrupt synthetic archive')
    with pytest.raises(KBError) as caught:sync.sync_file(kb,path)
    assert caught.value.code=='ARCHIVE_CORRUPT'
    assert archive.read_bytes()==b'corrupt synthetic archive'


def test_unchanged_sync_recovers_missing_archive(imported):
    from pathlib import Path
    kb,path=imported
    archive=Path(kb.rows('SELECT path FROM archives')[0]['path'])
    archive.unlink()
    sync.sync_file(kb,path)
    assert archive.read_bytes()==path.read_bytes()


def test_sequential_rollout_shards_keep_messages_distinct_and_retryable(tmp_path):
    kb=KB(tmp_path/'shards.sqlite3')
    first=tmp_path/'rollout-2026-01-01T00-00-00-chat.jsonl'
    second=tmp_path/'rollout-2026-01-02T00-00-00-chat_next.jsonl'
    save(first,[
        dict(type='session_meta',payload={'id':'sharded-chat'}),
        dict(type='response_item',timestamp='2026-01-01T00:00:01Z',payload=dict(type='message',role='user',content=[dict(type='input_text',text='first shard')])) ,
        dict(type='event_msg',payload={}),
        dict(type='event_msg',payload={}),
        dict(type='event_msg',payload={}),
        dict(type='event_msg',payload={}),
    ])
    save(second,[
        dict(type='session_meta',payload={'id':'sharded-chat'}),
        dict(type='response_item',timestamp='2026-01-02T00:00:01Z',payload=dict(type='message',role='user',content=[dict(type='input_text',text='second shard')])) ,
        dict(type='event_msg',payload={}),
        dict(type='response_item',timestamp='2026-01-02T00:00:02Z',payload=dict(type='message',role='assistant',content=[dict(type='output_text',text='second shard reply')])) ,
    ])

    first_result=sync.sync_file(kb,first,name='Synthetic',canonical='synthetic')
    first_message=kb.rows("SELECT id,seq,content FROM messages WHERE conversation_id='sharded-chat' AND content='first shard'")[0]
    second_result=sync.sync_file(kb,second)

    assert first_result['imported']==1
    assert second_result['imported']==2
    assert kb.rows("SELECT id,seq,content FROM messages WHERE conversation_id='sharded-chat' AND content='first shard'")==[first_message]
    messages=kb.rows("SELECT seq,content FROM messages WHERE conversation_id='sharded-chat' AND seq>0 ORDER BY seq")
    assert [row['content'] for row in messages]==['first shard','second shard','second shard reply']
    assert len({row['seq'] for row in messages})==3
    assert messages[1]['seq']>first_message['seq']
    assert sync.sync_file(kb,second)['unchanged'] is True
    assert len(kb.rows("SELECT id FROM messages WHERE conversation_id='sharded-chat' AND seq>0"))==3


def test_rollout_sources_are_processed_in_filename_order(tmp_path):
    home=tmp_path/'codex'
    late=home/'archived_sessions'/'rollout-2026-01-02T00-00-00-chat.jsonl'
    early=home/'sessions'/'rollout-2026-01-01T00-00-00-chat.jsonl'
    late.parent.mkdir(parents=True);early.parent.mkdir(parents=True)
    late.write_text('{}\n',encoding='utf-8');early.write_text('{}\n',encoding='utf-8')
    assert sync.sources(home)==[early,late]


def test_rewritten_or_truncated_shard_is_rejected_without_advancing_ledger(tmp_path):
    kb=KB(tmp_path/'shard-integrity.sqlite3')
    path=tmp_path/'rollout-2026-01-01T00-00-00-chat.jsonl'
    save(path,[
        dict(type='session_meta',payload={'id':'integrity-chat'}),
        dict(type='response_item',timestamp='2026-01-01T00:00:01Z',payload=dict(type='message',role='user',content=[dict(type='input_text',text='original')])) ,
        dict(type='event_msg',payload={}),
    ])
    sync.sync_file(kb,path,name='Synthetic',canonical='synthetic')
    before_state=kb.rows('SELECT * FROM sync_state')
    before_shards=kb.rows('SELECT * FROM sync_sources')
    before_messages=kb.rows('SELECT * FROM messages')
    before_archives=kb.rows('SELECT sha256 FROM archives ORDER BY sha256')

    save(path,[
        dict(type='session_meta',payload={'id':'integrity-chat'}),
        dict(type='response_item',timestamp='2026-01-01T00:00:01Z',payload=dict(type='message',role='user',content=[dict(type='input_text',text='rewritten')])) ,
        dict(type='event_msg',payload={}),
    ])
    with pytest.raises(KBError) as caught:
        sync.sync_file(kb,path)
    assert caught.value.code=='SOURCE_CHANGED'
    assert kb.rows('SELECT * FROM sync_state')==before_state
    assert kb.rows('SELECT * FROM sync_sources')==before_shards
    assert kb.rows('SELECT * FROM messages')==before_messages
    assert kb.rows('SELECT sha256 FROM archives ORDER BY sha256')==before_archives

    save(path,[dict(type='session_meta',payload={'id':'integrity-chat'})])
    with pytest.raises(KBError) as caught:
        sync.sync_file(kb,path)
    assert caught.value.code=='SOURCE_TRUNCATED'
    assert kb.rows('SELECT * FROM sync_state')==before_state
    assert kb.rows('SELECT * FROM sync_sources')==before_shards
    assert kb.rows('SELECT * FROM messages')==before_messages
    assert kb.rows('SELECT sha256 FROM archives ORDER BY sha256')==before_archives
