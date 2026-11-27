import asyncio, json
from jsonschema import Draft202012Validator
from pathlib import Path
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT=Path(__file__).resolve().parents[1]
PYTHON=ROOT/".venv"/"Scripts"/"python.exe"

def data(result):
    assert result.isError is False
    return json.loads(result.content[0].text)

def test_stdio_initialization_discovery_preferences_and_updates(tmp_path):
    async def run():
        db=tmp_path/"agent.sqlite3"
        prefs=tmp_path/"prefs.md"
        prefs.write_text("Teach in short steps; use Rust.",encoding="utf-8")
        params=StdioServerParameters(command=str(PYTHON),args=[str(ROOT/"server.py")],cwd=str(ROOT),
            env={"ALGORITHM_KB":str(db),"ALGORITHM_PREFERENCES":str(prefs)})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                init=await session.initialize()
                assert init.serverInfo.name=="algorithm-learning"
                listed = await session.list_tools()
                names={t.name for t in listed.tools}
                assert len(names) == 21
                for tool in listed.tools:
                    Draft202012Validator.check_schema(tool.inputSchema)
                search_schema = next(t.inputSchema for t in listed.tools if t.name == "search_knowledge")
                assert {"concepts", "topic_ids", "include_progress", "detail", "cursor"} <= set(search_schema["properties"])
                concept = data(await session.call_tool("search_concept_knowledge", {"concepts": ["network-flow"], "limit": 1}))
                assert concept["ok"] and "not_indexed" in json.dumps(concept)
                missing = data(await session.call_tool("read_concept_link", {"event_seq": 1}))
                assert not missing["ok"]
                assert data(await session.call_tool("get_concept_changes", {}))["ok"]
                assert not any("approve" in n or "import_concept" in n for n in names)
                required={"get_learning_preferences","register_conversation","get_context_manifest",
                    "get_topic_context","search_knowledge","update_learning","get_global_overview",
                    "search_concept_knowledge","read_concept_link","get_concept_changes"}
                assert required <= names
                pref=data(await session.call_tool("get_learning_preferences",{}))
                assert pref["ok"] and pref["data"]["text"]=="Teach in short steps; use Rust."
                reg=data(await session.call_tool("register_conversation",{"conversation_id":"test-chat-001",
                    "name":"Segment Tree Course","title":"Segment Tree Course"}))
                assert reg["ok"]
                topic=reg["data"]["topic_id"]
                manifest=data(await session.call_tool("get_context_manifest",{"conversation_id":"test-chat-001","current_only":True}))
                assert manifest["ok"] and manifest["data"]["current"]["topic_id"]==topic
                archived=data(await session.call_tool("record_conversation_update",{"conversation_id":"test-chat-001",
                    "request_id":"source-message-1","messages":[{"role":"user","content":"Learn segment trees",
                    "timestamp":"2026-11-26T12:00:00Z"}]}))
                assert archived["ok"]
                msg=archived["data"]["message_ids"][0]
                ctx=data(await session.call_tool("get_topic_context",{"topic_id":topic}))
                version=ctx["data"]["topic_version"]
                changes={"progress":{"append":{"taught":["range sum"],"evidence":[msg]}},
                    "knowledge":[{"data":{"title":"Range sum","content":"A segment tree supports range aggregation.",
                    "status":"candidate","evidence":[msg]}}]}
                update=data(await session.call_tool("update_learning",{"topic_id":topic,"conversation_id":"test-chat-001",
                    "expected_version":version,"request_id":"learning-update-1","changes":changes}))
                assert update["ok"],update
                found=data(await session.call_tool("search_knowledge",{"query":"segment tree","topic_id":topic,"limit":5}))
                assert found["ok"] and found["data"]
                overview=data(await session.call_tool("get_global_overview",{}))
                assert overview["ok"]
        assert db.exists()
    asyncio.run(run())
