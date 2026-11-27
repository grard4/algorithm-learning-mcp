import asyncio, json, os, socket, subprocess, time
from pathlib import Path
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/".venv"/"Scripts"/"python.exe"

def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1",0))
        return sock.getsockname()[1]

def test_streamable_http_initialization_and_tools(tmp_path):
    port=free_port()
    env=os.environ.copy()
    env.update(ALGORITHM_MCP_TRANSPORT="streamable-http",ALGORITHM_MCP_HOST="127.0.0.1",
        ALGORITHM_MCP_PORT=str(port),ALGORITHM_KB=str(tmp_path/"http.sqlite3"))
    proc=subprocess.Popen([str(PYTHON),str(ROOT/"server.py")],cwd=ROOT,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    async def run():
        try:
            last=None
            for _ in range(60):
                try:
                    async with streamable_http_client(f"http://127.0.0.1:{port}/mcp") as (read,write,_):
                        async with ClientSession(read,write) as session:
                            init=await session.initialize()
                            assert init.serverInfo.name=="algorithm-learning"
                            names={t.name for t in (await session.list_tools()).tools}
                            assert "get_learning_preferences" in names
                            pref=await session.call_tool("get_learning_preferences",{})
                            assert json.loads(pref.content[0].text)["ok"]
                            return
                except Exception as exc:
                    last=exc
                    await asyncio.sleep(.15)
            raise AssertionError(f"Streamable HTTP startup/handshake failed: {last}")
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill()
    asyncio.run(run())
