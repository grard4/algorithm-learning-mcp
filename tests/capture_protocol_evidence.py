import asyncio, json, tempfile, sys
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
ROOT=Path(__file__).resolve().parents[1]
async def main():
    (ROOT/".release-audit").mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT/".release-audit") as temp:
        params=StdioServerParameters(command=sys.executable,
            args=[str(ROOT/"server.py")],cwd=str(ROOT),env={"ALGORITHM_KB":str(Path(temp)/"evidence.sqlite3")})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                init=await session.initialize()
                listed=await session.list_tools()
                output={"server_name":init.serverInfo.name,"server_version":init.serverInfo.version,
                    "negotiated_protocol_version":init.protocolVersion,"tools":[{"name":t.name,"description":t.description,
                    "inputSchema":t.inputSchema} for t in listed.tools]}
        target=ROOT/"docs"/"evidence"/"stdio-tools-list.json"
        target.write_text(json.dumps(output,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
asyncio.run(main())
