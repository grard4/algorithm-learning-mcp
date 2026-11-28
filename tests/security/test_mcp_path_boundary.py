"""Exercise the real stdio MCP serialization boundary with synthetic local paths."""
import asyncio
import json
import sys
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from kb import now

ROOT = Path(__file__).resolve().parents[2]
WIN = r'C:\Users\private-person\course folder\secret.jsonl'
POSIX = '/home/private-person/course folder/secret.jsonl'


def test_all_public_reads_redact_paths_over_stdio(linked, tmp_path):
    kb, ctx, tid = linked
    nested = json.dumps({'nested': [{'cwd': WIN, 'other': POSIX}], 'safe': 'kept'})
    with kb.connect() as c:
        c.execute('UPDATE conversations SET cwd=?,source_path=?', (WIN, POSIX))
        c.execute('INSERT INTO discovery_candidates VALUES(?,?,?,?)', ('candidate', WIN, nested, now()))
        c.execute('UPDATE change_history SET after_json=? WHERE entity=?', (nested, 'conversations'))
    prefs = tmp_path/'prefs.md'
    prefs.write_text('Use ' + WIN + ' or ' + POSIX, encoding='utf-8')
    requests = {
        'get_learning_preferences': {}, 'get_course_rules': {},
        'get_sync_health': {}, 'get_update_history': {'full': True, 'limit': 100},
        'get_context_manifest': {'conversation_id': 'chat'},
        'get_topic_context': {'topic_id': tid, 'full': True},
        'get_topic_version': {'topic_id': tid},
        'get_context_delta': {'topic_id': tid, 'after_version': 0, 'full': True},
        'get_global_overview': {'full': True}, 'get_conversation_tree': {},
        'search_knowledge': {'query': 'synthetic'},
        'read_knowledge': {'knowledge_id': 'k'},
        'get_conversation_history': {'conversation_id': 'chat'},
        'detect_knowledge_conflicts': {},
        'search_concept_knowledge': {'concepts': ['synthetic']},
        'read_concept_link': {'event_seq': 1}, 'get_concept_changes': {},
    }

    async def run():
        params = StdioServerParameters(command=sys.executable, args=[str(ROOT/'server.py')],
            cwd=str(ROOT), env={'ALGORITHM_KB': str(kb.path), 'ALGORITHM_PREFERENCES': str(prefs)})
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                names = {t.name for t in (await session.list_tools()).tools}
                writes = {'register_conversation', 'update_learning', 'rollback_update',
                          'sync_conversation', 'record_conversation_update'}
                assert names - writes == set(requests)
                for name, args in requests.items():
                    response = await session.call_tool(name, args)
                    text = ''.join(x.text for x in response.content)
                    assert 'private-person' not in text, (name, text)
                    assert 'source_path' not in text and '"cwd"' not in text, (name, text)
                    assert not response.isError
                    assert json.loads(text)['ok'], (name, text)
                for args in ({}, {'full': False, 'after_id': 1, 'limit': 1}):
                    text = (await session.call_tool('get_update_history', args)).content[0].text
                    assert 'private-person' not in text
                # Includes framework argument validation before application dispatch.
                for name, args in [('read_knowledge', {'knowledge_id': WIN}),
                                   ('get_update_history', {'limit': POSIX}),
                                   ('sync_conversation', {'conversation_id': 'chat'})]:
                    result = await session.call_tool(name, args)
                    assert 'private-person' not in str(result), name
                health = json.loads((await session.call_tool('get_sync_health', {})).content[0].text)
                assert health['data']['discovery'][0]['source_id']
                with kb.connect() as c:
                    c.execute('UPDATE messages SET content=?', ('prefix ' + POSIX + ' suffix',))
                    row = json.loads(c.execute("SELECT data FROM knowledge_items WHERE id='k'").fetchone()[0])
                    row['content'] = 'prefix ' + WIN + ' suffix'
                    row['metadata'] = {'source_path': WIN, 'nested': json.dumps({'cwd': POSIX, 'safe': 'kept'})}
                    c.execute("UPDATE knowledge_items SET data=? WHERE id='k'", (json.dumps(row),))
                for name, args, field in [
                    ('get_conversation_history', {'conversation_id': 'chat', 'message_id': 'msg'}, 'content'),
                    ('read_knowledge', {'knowledge_id': 'k'}, 'text')]:
                    offset, text = 0, ''
                    while offset is not None:
                        response = await session.call_tool(name, dict(args, offset=offset, chars=3))
                        page = json.loads(response.content[0].text)['data']
                        page = page['message'] if name == 'get_conversation_history' else page
                        text += page[field]
                        offset = page['next_offset']
                    assert 'private-person' not in text and 'prefix' in text and 'suffix' in text
                offset, text = 0, ''
                while offset is not None:
                    response = await session.call_tool('read_knowledge',
                        {'knowledge_id': 'k', 'field': 'metadata', 'offset': offset, 'chars': 3})
                    page = json.loads(response.content[0].text)['data']
                    text += page['text']
                    offset = page['next_offset']
                assert 'source_path' not in text and 'cwd' not in text and 'private-person' not in text
                assert 'kept' in text
    asyncio.run(run())
    assert kb.rows('SELECT cwd,source_path FROM conversations')[0] == {'cwd': WIN, 'source_path': POSIX}
    assert kb.rows('SELECT source_path FROM discovery_candidates')[0]['source_path'] == WIN
    assert json.loads(kb.rows("SELECT after_json FROM change_history WHERE entity='conversations'")[0]['after_json'])['safe'] == 'kept'


def test_paginated_text_redacted_before_slicing(linked):
    # Splitting inside a path must not let sequential page reads reconstruct it.
    kb, ctx, _ = linked
    with kb.connect() as c:
        c.execute('UPDATE messages SET content=?', ('prefix ' + POSIX + ' suffix',))
        data = json.loads(c.execute("SELECT data FROM knowledge_items WHERE id='k'").fetchone()[0])
        data['content'] = 'prefix ' + WIN + ' suffix'
        c.execute("UPDATE knowledge_items SET data=? WHERE id='k'", (json.dumps(data),))
    for reader in (lambda offset: ctx.read('k', offset=offset, chars=3),
                   lambda offset: ctx.history('chat', message_id='msg', offset=offset, chars=3)['message']):
        offset = 0
        pieces = []
        while offset is not None:
            page = reader(offset)
            pieces.append(page.get('text', page.get('content')))
            offset = page['next_offset']
        assert 'private-person' not in ''.join(pieces)
        assert 'prefix' in ''.join(pieces) and 'suffix' in ''.join(pieces)
