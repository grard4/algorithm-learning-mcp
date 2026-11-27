"""Security expectations recorded before fixes; synthetic data only."""
import importlib
import json
import pytest
import zstandard
from kb import KB, KBError, now
from context import Context
from sync import read_bytes


@pytest.fixture
def service(tmp_path, monkeypatch):
    s = importlib.import_module('server')
    k = KB(tmp_path/'round2.sqlite3')
    monkeypatch.setattr(s, 'kb', k)
    monkeypatch.setattr(s, 'context', Context(k))
    a = k.register('Alpha','','a','Alpha')['topic_id']
    b = k.register('Beta','','b','Beta')['topic_id']
    for cid in ('a','b'):
        with k.connect() as c:
            c.execute('INSERT INTO archives VALUES(?,?,?,?,?,?)',(cid,cid,'synthetic-'+cid,'synthetic',1,now()))
            c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)',('m'+cid,cid,1,'user',now(),'proof',cid,1))
    return s,k,a,b


def test_a01_legacy_wrong_topic(service):
    s,k,a,b=service
    result=s.add_knowledge(b,{'title':'x','content':'x','evidence':['ma']},'bad','a')
    assert not result['ok']
    assert not k.rows('SELECT * FROM knowledge_items')


def test_a01_legacy_external_evidence(service):
    s,k,a,b=service
    assert not s.record_learning_task(a,{'title':'x','status':'pending','evidence':['mb']},'bad','a')['ok']


def test_a02_oserror_path(service, tmp_path):
    s,k,a,b=service
    path=tmp_path/'private-location'/'missing.jsonl'
    with k.connect() as c: c.execute('UPDATE conversations SET source_path=? WHERE id=?',(str(path),'a'))
    result=s.sync_conversation('a')
    assert not result['ok']
    assert 'private-location' not in json.dumps(result)


@pytest.mark.parametrize('case',['timestamp','message_bytes','message_count','nested'])
def test_a03_normalized_limits(service, case):
    s,k,a,b=service
    m={'role':'user','content':'x','timestamp':now()}
    messages=[m]
    if case=='timestamp':m['timestamp']='not-a-date'
    if case=='message_bytes':m['content']='x'*(256*1024+1)
    if case=='message_count':messages=[m]*129
    if case=='nested':m['extra']={'nested':{'extra':'unrecognized'}}
    before=k.rows('SELECT * FROM messages')
    result=s.record_conversation_update('a',messages,'bad')
    assert not result['ok']
    assert k.rows('SELECT * FROM messages')==before


def test_a04_compression_ratio(tmp_path):
    p=tmp_path/'bomb.zst'
    p.write_bytes(zstandard.ZstdCompressor().compress(b'x'*(2*1024*1024)))
    with pytest.raises(KBError):read_bytes(p)


def test_a07_rejected_idempotency_leaves_no_archive(service):
    s,k,a,b=service
    msg=[{'role':'user','content':'first','timestamp':now()}]
    assert s.record_conversation_update('a',msg,'same')['ok']
    before=set(k.path.parent.rglob('*.normalized.json'))
    msg[0]['content']='second'
    assert not s.record_conversation_update('a',msg,'same')['ok']
    assert set(k.path.parent.rglob('*.normalized.json'))==before
