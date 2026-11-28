"""Install/upgrade/CLI smoke against the actual released v0.2.1 source tree.

Requires git plus the v0.2.1 tag; all databases and archives are synthetic/temp.
"""
import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'df6c3401d5829cbf99b2734120b9440397acc633'


def snapshot(path):
    with contextlib.closing(sqlite3.connect(path)) as c:
        names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        return {n: sorted(c.execute('SELECT * FROM "' + n + '"').fetchall(), key=repr) for n in names}


def run():
    commit = subprocess.check_output(['git', 'rev-parse', 'v0.2.1^{commit}'], cwd=ROOT, text=True).strip()
    assert commit == BASELINE
    archive = subprocess.check_output(['git', 'archive', '--format=zip', BASELINE], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix='algorithm-v022-upgrade-') as temp:
        root = Path(temp)
        baseline = root/'baseline'
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            for name in z.namelist():
                assert not Path(name).is_absolute() and '..' not in Path(name).parts
            z.extractall(baseline)
        db = root/'learning.sqlite3'
        env = {k: v for k, v in os.environ.items() if not k.startswith('ALGORITHM_')}
        env.update(ALGORITHM_KB=str(db), ALGORITHM_PREFERENCES=str(root/'missing.md'))
        init = """
import json
from pathlib import Path
from kb import KB
from sync import sync_file
k=KB()
p=k.path.parent/'synthetic.jsonl'
p.write_text(json.dumps({'type':'session_meta','payload':{'id':'synthetic'}})+'\\n'+json.dumps({'type':'response_item','timestamp':'2026-01-01T00:00:00Z','payload':{'type':'message','role':'user','content':[{'type':'text','text':'proof'}]}})+'\\n',encoding='utf-8')
sync_file(k,p,name='Synthetic')
"""
        subprocess.run([sys.executable, '-c', init], cwd=baseline, env=env, check=True, capture_output=True)
        before = snapshot(db)
        checks = []

        def cli(*args, expected=0):
            result = subprocess.run([sys.executable, 'cli.py', *args], cwd=ROOT, env=env,
                                    capture_output=True, text=True, encoding='utf-8', timeout=30)
            assert result.returncode == expected, (args[0], result.returncode, result.stderr)
            checks.append({'command': args[0], 'exit_code': result.returncode})
            return json.loads(result.stdout)

        health = cli('call', 'get_sync_health')
        assert health['ok'] and health['data']['integrity'] == [{'integrity_check': 'ok'}]
        assert snapshot(db) == before, 'v0.2.1 data or schema changed during upgrade'
        verified = cli('verify')
        assert verified['integrity'] == [{'integrity_check': 'ok'}]
        assert verified['foreign_keys'] == [] and verified['bad_archives'] == []
        cli('backup', str(root/'backup.sqlite3'))
        cli('restore', str(root/'backup.sqlite3'), str(root/'restored.sqlite3'))
        with contextlib.closing(sqlite3.connect(root/'restored.sqlite3')) as c:
            assert c.execute('PRAGMA integrity_check').fetchall() == [('ok',)]
            assert c.execute('PRAGMA foreign_key_check').fetchall() == []
        cli('call', 'get_topic_context', expected=1)
        env['ALGORITHM_KB'] = str(root/'fresh.sqlite3')
        assert cli('call', 'get_context_manifest')['ok']
        assert (root/'fresh.sqlite3').exists()
        return {'baseline': BASELINE, 'platform': sys.platform, 'python': sys.version.split()[0],
                'synthetic_data_preserved': True, 'fresh_initialization': True,
                'archive_hashes_valid': True, 'integrity': 'ok', 'foreign_key_errors': 0, 'checks': checks}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    result = run()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
