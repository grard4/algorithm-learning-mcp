import contextlib
import sqlite3
import pytest
import compact_api
import notifications
from concept_reader import ReadError
from optimized_reads import ReadCache


def query(kb,fn):
    with contextlib.closing(sqlite3.connect(kb.path)) as c:
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
        return fn(c)


def test_cache_hit_ttl_and_copy(linked):
    kb,_,_=linked
    ticks=[0]
    cache=ReadCache(compact_api.search,notifications.health,ReadError,'test',ttl=2,clock=lambda:ticks[0])
    first=query(kb,lambda c:cache.query(c,['synthetic']))
    assert first['groups'][0]['items'][0]['reusable']
    second=query(kb,lambda c:cache.query(c,['synthetic']))
    assert first==second and cache.hits==1
    second['groups'].clear()
    assert query(kb,lambda c:cache.query(c,['synthetic']))==first
    ticks[0]=3
    assert query(kb,lambda c:cache.query(c,['synthetic']))==first
    assert cache.misses==2


@pytest.mark.parametrize('mutation',[
    "UPDATE knowledge_items SET version=version+1 WHERE id='k'",
    "UPDATE messages SET content='changed' WHERE id='msg'",
    "DELETE FROM knowledge_items WHERE id='k'",
    "DELETE FROM messages WHERE id='msg'",
])
def test_source_mutations_invalidate_cached_proofs(linked,mutation):
    kb,_,_=linked
    cache=ReadCache(compact_api.search,notifications.health,ReadError,'test')
    first=query(kb,lambda c:cache.query(c,['synthetic']))
    cursor=query(kb,lambda c:notifications.changes(c))['cursor']
    # An independent connection models a writer in another process.
    with kb.connect() as c: c.execute(mutation)
    second=query(kb,lambda c:cache.query(c,['synthetic']))
    assert first!=second and cache.misses==2
    assert not second['groups'][0]['items'][0]['reusable']
    delta=query(kb,lambda c:notifications.changes(c,cursor,limit=1))
    assert delta['changes'][0]['concept_id']=='c'


def test_schema_tamper_fails_on_cache_hit(linked):
    kb,_,_=linked
    cache=ReadCache(compact_api.search,notifications.health,ReadError,'test')
    query(kb,lambda c:cache.query(c,['synthetic']))
    with kb.connect() as c: c.execute('DROP TRIGGER r3_messages_update')
    with pytest.raises(notifications.NoticeError,match='JOURNAL_SCHEMA_CHANGED'):
        query(kb,lambda c:cache.query(c,['synthetic']))


def test_lru_capacity_and_bytes(linked):
    kb,_,_=linked
    cache=ReadCache(compact_api.search,notifications.health,ReadError,'test',max_entries=2,max_bytes=2000)
    for name in ['one','two','three']:
        query(kb,lambda c:cache.query(c,[name]))
    assert len(cache.entries)<=2 and cache.bytes<=2000
    assert cache.bytes==sum(item[2] for item in cache.entries.values())


def test_notice_cursor_epoch_and_tampering(linked):
    kb,_,_=linked
    cursor=query(kb,lambda c:notifications.changes(c))['cursor']
    with kb.connect() as c: c.execute("UPDATE r3_meta SET epoch='new-epoch'")
    with pytest.raises(notifications.NoticeError,match='CURSOR_EPOCH_CHANGED'):
        query(kb,lambda c:notifications.changes(c,cursor))
    with pytest.raises(notifications.NoticeError):
        query(kb,lambda c:notifications.changes(c,'not-base64'))
