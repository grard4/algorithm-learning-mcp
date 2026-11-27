"""All tests use synthetic data under pytest's temporary directory."""
import json
import sqlite3
import pytest
from kb import KB, now
from context import Context
from concept_reader import text_hash


@pytest.fixture(autouse=True)
def isolate_defaults(tmp_path, monkeypatch):
    for key in list(__import__('os').environ):
        if key.startswith('ALGORITHM_'): monkeypatch.delenv(key)
    monkeypatch.setenv('ALGORITHM_KB',str(tmp_path/'default.sqlite3'))
    monkeypatch.setenv('ALGORITHM_PREFERENCES',str(tmp_path/'missing-preferences.md'))
    yield
    for path in tmp_path.rglob('*.sqlite3'):
        with sqlite3.connect(path) as c:
            assert c.execute('PRAGMA integrity_check').fetchall()==[('ok',)],path.name
            assert c.execute('PRAGMA foreign_key_check').fetchall()==[],path.name


@pytest.fixture
def linked(tmp_path):
    kb=KB(tmp_path/'linked.sqlite3')
    ctx=Context(kb)
    tid=ctx.register('Synthetic topic','','chat')['topic_id']
    with kb.connect() as c:
        c.execute('INSERT INTO archives VALUES(?,?,?,?,?,?)',('archive','chat','synthetic.jsonl','synthetic',1,now()))
        c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)',('msg','chat',1,'user','time','proof','archive',1))
    ctx.update(tid,'chat',ctx.version(tid)['topic_version'],'knowledge',{'knowledge':[{'id':'k','data':{
        'title':'Synthetic','content':'searchable synthetic claim','evidence':['msg']}}]})
    with kb.connect() as c:
        data=c.execute("SELECT data FROM knowledge_items WHERE id='k'").fetchone()[0]
        proof={'source':{'knowledge_id':'k','knowledge_version':1,'knowledge_data_sha256':text_hash(data),
                'source_conversation':'chat','topic_id':tid,'evidence':[dict(message_id='msg',archive_sha256='archive',
                content_sha256=text_hash('proof'),locator=1,role='user',seq=1,conversation_id='chat')]}}
        c.execute('INSERT INTO c_concepts VALUES(?,?,?,?)',('c','synthetic','Synthetic',now()))
        c.execute('INSERT INTO c_requests VALUES(?,?,?,?,?)',('r','hash','test',now(),'{}'))
        c.execute('INSERT INTO c_events(concept_id,version,request_id,kind,data,topic_id,conversation_id,knowledge_id,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
            ('c',1,'r','link',json.dumps(proof),tid,'chat','k',now()))
    return kb,ctx,tid
