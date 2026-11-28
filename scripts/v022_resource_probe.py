"""Reproducible synthetic probes; never open the installed service or its data."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from round2_resource_probe import peak_rss

CASES = ('empty_frames', 'small_frames', 'large_output', 'large_sync', 'discovery', 'history', 'redaction_noise')


def probe(case):
    import zstandard
    import sync
    from kb import KB, KBError, now
    with tempfile.TemporaryDirectory(prefix='algorithm-v022-') as temp:
        root = Path(temp)
        for key in list(os.environ):
            if key.startswith('ALGORITHM_'):
                del os.environ[key]
        os.environ.update(ALGORITHM_KB=str(root/'test.sqlite3'), ALGORITHM_PREFERENCES=str(root/'missing'))
        kb = KB()
        size, units, status, reads = 0, 0, 'accepted', None
        if case == 'redaction_noise':
            from public_response import public_response
            value = chr(92) * 500000
            size = units = len(value)
            start = time.perf_counter()
            assert public_response({'text': value}) == {'text': value}
        elif case in ('empty_frames', 'small_frames', 'large_output'):
            path = root/'source.zst'
            if case == 'large_output':
                raw = os.urandom(1024 * 1024) * 33
                units = len(raw)
                path.write_bytes(zstandard.ZstdCompressor().compress(raw))
                del raw
            else:
                units = 200000
                path.write_bytes(zstandard.ZstdCompressor().compress(b'' if case == 'empty_frames' else b'x') * units)
            size = path.stat().st_size
            start = time.perf_counter()
            try:
                sync.read_bytes(path)
            except KBError as exc:
                status = exc.code
            assert status == 'TOO_LARGE'
        elif case == 'large_sync':
            path = root/'source.jsonl'
            with path.open('w', encoding='utf-8', newline='\n') as f:
                f.write(json.dumps({'type': 'session_meta', 'payload': {'id': 'synthetic'}}) + '\n')
                line = json.dumps({'type': 'event_msg', 'payload': {'text': 'x' * 10000}}) + '\n'
                units = 1500
                for _ in range(units):
                    f.write(line)
            size = path.stat().st_size
            start = time.perf_counter()
            result = sync.sync_file(kb, path, name='Synthetic')
            assert result['conversation_id'] == 'synthetic'
            assert kb.rows('SELECT line_count FROM sync_state')[0]['line_count'] == units + 1
        elif case == 'discovery':
            home = root/'home'
            (home/'sessions').mkdir(parents=True)
            units = 5000
            for n in range(units):
                (home/'sessions'/f'rollout-{n}.jsonl').touch()
            sync.ROOT = root
            start = time.perf_counter()
            reads = []
            for _ in range(5):
                tick = time.perf_counter()
                assert sync.run(kb, home, discover=True) == []
                reads.append({'seconds': time.perf_counter()-tick, 'peak_rss_bytes': peak_rss()})
            size = sum(p.stat().st_size for p in (root/'config').glob('*'))
        else:
            registration = kb.register('Synthetic', '', 'chat', 'Synthetic')
            units = 5000
            payload = json.dumps({'nested': {'cwd': '/home/synthetic-private/data',
                                           'source_path': r'C:\synthetic-private\data'}, 'safe': 'x' * 512})
            size = len(payload.encode()) * units
            with kb.connect() as c:
                c.executemany('INSERT INTO change_history(update_id,entity,entity_id,after_json) VALUES(?,?,?,?)',
                    [(registration['update_id'], 'probe', 'bulk', payload)] * units)
            start = time.perf_counter()

            async def read_history():
                from mcp import ClientSession
                from mcp.client.stdio import StdioServerParameters, stdio_client
                params = StdioServerParameters(command=sys.executable, args=[str(ROOT/'server.py')], cwd=str(ROOT),
                    env={'ALGORITHM_KB': str(kb.path), 'ALGORITHM_PREFERENCES': str(root/'missing')})
                count, cursor = 0, 0
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        while True:
                            result = await session.call_tool('get_update_history',
                                {'entity_id': 'bulk', 'after_id': cursor, 'limit': 100, 'full': True})
                            text = result.content[0].text
                            assert 'synthetic-private' not in text
                            rows = json.loads(text)['data']
                            if not rows:
                                break
                            count += len(rows)
                            cursor = rows[-1]['id']
                assert count == units
            asyncio.run(read_history())
        elapsed = time.perf_counter()-start
        assert kb.rows('PRAGMA integrity_check') == [{'integrity_check': 'ok'}]
        assert kb.rows('PRAGMA foreign_key_check') == []
        assert not list(root.rglob('.pending-*')) and not list(root.rglob('.discovery-*'))
        result = dict(case=case, input_bytes=size, units=units, elapsed_seconds=elapsed,
            peak_rss_bytes=peak_rss(), status=status, repeated_scans=reads,
            integrity='ok', foreign_key_errors=0, pending_files=0,
            measured_at=now())
    result['temporary_directory_removed'] = not root.exists()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.case:
        print(json.dumps(probe(args.case)))
    else:
        rows = []
        for case in CASES:
            child = subprocess.run([sys.executable, __file__, '--case', case], cwd=ROOT,
                capture_output=True, text=True, timeout=120)
            if child.returncode:
                raise RuntimeError(case + ': ' + child.stderr[-4000:])
            rows.append(json.loads(child.stdout))
        report = {'platform': sys.platform, 'python': sys.version.split()[0],
            'memory_scope': 'Whole probe child peak RSS including imports and input setup. History MCP server child RSS is NOT included; no aggregate memory guarantee.',
            'cases': rows}
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, indent=2))
