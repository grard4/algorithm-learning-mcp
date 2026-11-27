import asyncio
import importlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from kb import KBError
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT=Path(__file__).resolve().parents[2]
NAMES=('update_topic_progress','add_knowledge','update_knowledge','record_learning_task','record_learning_result','add_knowledge_relation')

@pytest.mark.parametrize('name',NAMES)
def test_retired_write_all_entry_points(name,tmp_path):
    s=importlib.import_module('server')
    fn=getattr(s,name)
    payload={p.name:({} if p.name=='data' else 0 if p.name=='expected_version' else 'synthetic') for p in inspect.signature(fn).parameters.values() if p.default is inspect.Parameter.empty}
    assert fn(**payload)['error']['code']=='LEGACY_WRITE_DISABLED'
    with pytest.raises(KBError) as e:fn.__wrapped__(**payload)
    assert e.value.code=='LEGACY_WRITE_DISABLED'
    arg=tmp_path/'args.json';arg.write_text(json.dumps(payload),encoding='utf-8')
    env=dict(os.environ,ALGORITHM_KB=str(tmp_path/'cli.sqlite3'),ALGORITHM_LEGACY_TOOLS='1')
    proc=subprocess.run([sys.executable,str(ROOT/'cli.py'),'call',name,'--args-file',str(arg)],cwd=ROOT,env=env,capture_output=True,text=True)
    assert json.loads(proc.stdout)['error']['code']=='LEGACY_WRITE_DISABLED'

def test_actual_legacy_discovery_and_direct_transport_rejection(tmp_path):
    async def run():
        p=StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],cwd=str(ROOT),env={'ALGORITHM_KB':str(tmp_path/'legacy.sqlite3'),'ALGORITHM_LEGACY_TOOLS':'1'})
        async with stdio_client(p) as (r,w):
            async with ClientSession(r,w) as session:
                await session.initialize()
                names={x.name for x in (await session.list_tools()).tools}
                assert not names.intersection(NAMES)
                assert {'get_topic_progress','list_all_topics','get_knowledge_detail','update_learning'}<=names
                for name in NAMES:
                    result=await session.call_tool(name,{})
                    assert result.isError
    asyncio.run(run())
