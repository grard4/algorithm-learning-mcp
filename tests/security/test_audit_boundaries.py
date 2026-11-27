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
