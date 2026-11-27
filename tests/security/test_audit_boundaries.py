"""合成证据；这些断言在审计基线应暴露缺陷，修复后作为回归。"""
import json
import pytest
from kb import KB, KBError, now
from context import Context


@pytest.fixture
def records(tmp_path):
    kb = KB(tmp_path / 'audit.sqlite3')
    ctx = Context(kb)
    a = ctx.register('Audit Alpha', '', 'chat-a')['topic_id']
    b = ctx.register('Audit Beta', '', 'chat-b')['topic_id']
    ctx.register('', '', 'chat-a2', topic_id=a)
    with kb.connect() as c:
        for cid in ('chat-a', 'chat-a2', 'chat-b'):
            c.execute('INSERT INTO archives VALUES(?,?,?,?,?,?)', (cid, cid, cid+'.jsonl', 'synthetic', 1, now()))
            c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)', ('msg-'+cid, cid, 1, 'user', now(), 'synthetic evidence', cid, 1))
    yield kb, ctx, a, b
    assert kb.rows('PRAGMA integrity_check')[0]['integrity_check'] == 'ok'
    assert kb.rows('PRAGMA foreign_key_check') == []


def update(ctx, topic, cid, data):
    return ctx.update(topic, cid, ctx.version(topic)['topic_version'], 'audit-update', {'knowledge': [{'data': data}]})


def knowledge(ref='msg-chat-a', **extra):
    return dict(title='Synthetic', content='Synthetic claim', evidence=[ref], **extra)


def test_a02_wrong_topic_rejected(records):
    kb, ctx, a, b = records
    with pytest.raises(KBError, match='专题'):
        update(ctx, b, 'chat-a', knowledge())
    assert not kb.rows('SELECT * FROM knowledge_items')


def test_a03_implicit_external_evidence_rejected(records):
    kb, ctx, a, b = records
    with pytest.raises(KBError):
        update(ctx, a, 'chat-a', knowledge('msg-chat-b'))


def test_a03_forged_source_rejected(records):
    kb, ctx, a, b = records
    with pytest.raises(KBError):
        update(ctx, a, 'chat-a', knowledge(source_conversation='chat-b'))


def test_same_topic_cross_chat_allowed(records):
    kb, ctx, a, b = records
    assert update(ctx, a, 'chat-a', knowledge('msg-chat-a2'))


def test_explicit_external_reference_allowed(records):
    kb, ctx, a, b = records
    assert update(ctx, a, 'chat-a', knowledge('msg-chat-b', evidence_sources={
        'msg-chat-b': {'conversation_id': 'chat-b', 'topic_id': b, 'scope': 'cross_topic'}}))


def test_forged_external_locator_rejected(records):
    kb, ctx, a, b = records
    with pytest.raises(KBError):
        update(ctx, a, 'chat-a', knowledge('msg-chat-b', evidence_sources={
            'msg-chat-b': {'conversation_id': 'chat-a', 'topic_id': b, 'scope': 'cross_topic'}}))


def test_cross_topic_relation_remains_allowed(records):
    kb, ctx, a, b = records
    for tid, cid, ident in [(a,'chat-a','ka'),(b,'chat-b','kb')]:
        ctx.update(tid,cid,ctx.version(tid)['topic_version'],'create-'+cid,
                   {'knowledge':[{'id':ident,'data':knowledge('msg-'+cid)}]})
    assert ctx.update(a,'chat-a',ctx.version(a)['topic_version'],'rel',
        {'relations':[dict(source_id='ka',target_id='kb',kind='related',reason='explicit reference')]})


@pytest.mark.parametrize('forged', [False, True])
def test_dedup_preserves_valid_external_sources(records, forged):
    kb, ctx, a, b = records
    origin = {'conversation_id': 'chat-b', 'topic_id': b, 'scope': 'cross_topic'}
    ctx.update(a, 'chat-a', ctx.version(a)['topic_version'], 'initial',
        {'knowledge': [{'id': 'original', 'data': knowledge('msg-chat-b',
            evidence_sources={'msg-chat-b': origin})}]})
    before = kb.rows("SELECT * FROM knowledge_items WHERE id='original'")[0]
    version = ctx.version(a)
    data = knowledge()
    if forged:
        data['evidence_sources'] = {'msg-chat-b': {
            'conversation_id': 'chat-a', 'topic_id': a, 'scope': 'same_topic'}}
        with pytest.raises(KBError) as exc:
            update(ctx, a, 'chat-a', data)
        assert exc.value.code == 'VALIDATION_ERROR'
        assert kb.rows("SELECT * FROM knowledge_items WHERE id='original'")[0] == before
        assert ctx.version(a) == version
    else:
        update(ctx, a, 'chat-a', data)
        row = kb.rows("SELECT * FROM knowledge_items WHERE id='original'")[0]
        saved = json.loads(row['data'])
        assert row['version'] == before['version'] + 1
        assert saved['evidence'] == ['msg-chat-b', 'msg-chat-a']
        assert saved['evidence_sources'] == {'msg-chat-b': origin}
