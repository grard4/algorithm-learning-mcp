import json
import pytest
from kb import KB, KBError, now
from context import Context


def test_knowledge_cap_is_disclosed_and_topic_filter_recovers(tmp_path):
    kb=KB(tmp_path/'search.sqlite3');ctx=Context(kb)
    a=ctx.register('Alpha','','a')['topic_id'];b=ctx.register('Beta','','b')['topic_id']
    with kb.connect() as c:
        c.executemany('INSERT INTO knowledge_items VALUES(?,?,?,?,?)',[(f'{i:06}',a,1,json.dumps({'title':'other','content':'other'}),now()) for i in range(5000)])
        c.execute('INSERT INTO knowledge_items VALUES(?,?,?,?,?)',('z-last',b,1,json.dumps({'title':'needle','content':'needle'}),now()))
    result=ctx.search(query='needle')
    assert result['coverage']=='incomplete'
    assert result['items']==[]
    filtered=ctx.search(query='needle',topic_id=b)
    assert filtered['items'][0]['id']=='z-last'
    assert filtered['coverage']!='incomplete'


def test_history_cap_disclosed_and_batch_limits_are_independent(tmp_path):
    kb=KB(tmp_path/'search.sqlite3');ctx=Context(kb)
    tid=ctx.register('Alpha','','a')['topic_id']
    with kb.connect() as c:
        c.execute('INSERT INTO archives VALUES(?,?,?,?,?,?)',('archive','a','synthetic','synthetic',1,now()))
        c.executemany('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)',[(str(i),'a',i+1,'user',now(),'needle other','archive',i+1) for i in range(2001)])
    first=ctx.search(concepts=['needle','other'],limit=2,include_progress=False)
    assert first['coverage']=='incomplete'
    assert [len(g['items']) for g in first['groups']]==[2,2]
    second=ctx.search(concepts=['needle','other'],limit=2,include_progress=False,cursor=first['next_cursor'])
    for i in range(2):
        assert {x['message_id'] for x in first['groups'][i]['items']}.isdisjoint(x['message_id'] for x in second['groups'][i]['items'])
    with pytest.raises(KBError):
        ctx.search(concepts=['different','other'],limit=2,include_progress=False,cursor=first['next_cursor'])


def test_cursor_stale_and_malicious_query(linked):
    kb,ctx,tid=linked
    for i in range(3): kb.write('knowledge_items','extra'+str(i),{'title':'searchable','content':'searchable'},'extra'+str(i),'test',topic_id=tid)
    first=ctx.search(query='searchable',limit=1)
    assert first['next_cursor']
    kb.write('knowledge_items','extra0',{'title':'changed','content':'searchable'},'edit','test',expected_version=1)
    with pytest.raises(KBError,match='版本'):
        ctx.search(query='searchable',limit=1,cursor=first['next_cursor'])
    assert ctx.search(query="' OR 1=1 --")['items']==[]
    assert kb.rows('SELECT count(*) n FROM knowledge_items')[0]['n']==4
