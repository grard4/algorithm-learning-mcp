import os
import subprocess
import sys
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('host', ['0.0.0.0','::','192.0.2.1'])
def test_unsafe_remote_startup_rejected(tmp_path, host):
    env=os.environ.copy()
    for key in list(env):
        if key.startswith('ALGORITHM_'): env.pop(key)
    env.update(ALGORITHM_KB=str(tmp_path/'test.sqlite3'), ALGORITHM_MCP_TRANSPORT='streamable-http', ALGORITHM_MCP_HOST=host)
    # 拦截真正监听；仅验证入口的实际启动分支，不开放外部网络端口。
    code="from mcp.server.fastmcp import FastMCP; FastMCP.run=lambda self,**kw: print('RUN_ALLOWED'); import runpy; runpy.run_path('server.py',run_name='__main__')"
    proc=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,capture_output=True,text=True,timeout=30)
    assert proc.returncode != 0, proc.stdout
    assert 'RUN_ALLOWED' not in proc.stdout
