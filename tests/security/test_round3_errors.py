import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from errors import error_response
from kb import KBError

ROOT=Path(__file__).resolve().parents[2]

@pytest.mark.parametrize('secret',[r'C:\Users\private\learning.sqlite3','/home/private/learning.sqlite3'])
@pytest.mark.parametrize('kind',['identifier','validation'])
def test_public_errors_real_cli_and_mcp(linked,tmp_path,secret,kind):
    kb,ctx,tid=linked
    tool='get_topic_context';payload={'topic_id':secret};code='NOT_FOUND'
    if kind=='validation':
        tool='update_learning';code='VALIDATION_ERROR'
        payload=dict(topic_id=tid,conversation_id='chat',expected_version=ctx.version(tid)['topic_version'],request_id='bad',
                     changes={'tasks':[{'data':{'title':'test','status':secret,'evidence':['msg']}}],secret:True})
    arg=tmp_path/'args.json';arg.write_text(json.dumps(payload),encoding='utf-8')
    p=subprocess.run([sys.executable,'cli.py','call',tool,'--args-file',str(arg)],cwd=ROOT,
                     env=dict(os.environ,ALGORITHM_KB=str(kb.path)),capture_output=True,text=True)
    assert p.returncode==1
    result=json.loads(p.stdout)
    async def run():
        params=StdioServerParameters(command=sys.executable,args=[str(ROOT/'server.py')],cwd=str(ROOT),env={'ALGORITHM_KB':str(kb.path)})
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as session:
                await session.initialize()
                response=await session.call_tool(tool,payload)
                return json.loads(response.content[0].text)
    transported=asyncio.run(run())
    for response in (result,transported):
        assert response['error']['code']==code
        assert secret not in str(response)
        assert 'private' not in str(response)
        if kind=='validation':
            assert response['error']['details']
            assert any(row['path']=='changes.tasks[0].data.status' for row in response['error']['details'])
    assert 'private' not in p.stderr

def test_business_diagnostics(caplog):
    result=error_response(KBError('LEGACY_WRITE_DISABLED','请使用 update_learning'))
    assert result['error']['message']=='请使用 update_learning'
    assert 'LEGACY_WRITE_DISABLED' in caplog.text and 'KBError' in caplog.text

@pytest.mark.parametrize('expression,code,type_name',[
    ("PermissionError(13, r'C:\\Users\\private\\db')",'PERMISSION_DENIED','PermissionError'),
    ("FileNotFoundError(2, '/home/private/db')",'SOURCE_UNAVAILABLE','FileNotFoundError'),
    ("sqlite3.OperationalError('/tmp/private/db')",'DATABASE','OperationalError'),
    ("RuntimeError('/tmp/private/data')",'INTERNAL_ERROR','RuntimeError')])
def test_transport_system_errors(tmp_path,expression,code,type_name):
    setup="import server,sqlite3\ndef fail(*a,**kw):\n raise "+expression+"\nserver.kb.rows=fail\n"
    env=dict(os.environ,ALGORITHM_KB=str(tmp_path/'system.sqlite3'))
    cli=setup+"import runpy,sys\nsys.argv=['cli.py','call','sync_conversation','--args-file',sys.argv[1]]\nrunpy.run_path('cli.py',run_name='__main__')"
    arg=tmp_path/'args.json';arg.write_text('{"conversation_id":"chat"}',encoding='utf-8')
    p=subprocess.run([sys.executable,'-c',cli,str(arg)],cwd=ROOT,env=env,capture_output=True,text=True)
    assert p.returncode==1
    assert json.loads(p.stdout)['error']['code']==code
    assert code in p.stderr and type_name in p.stderr
    assert 'private' not in p.stdout+p.stderr
    async def run():
        params=StdioServerParameters(command=sys.executable,args=['-c',setup+"server.mcp.run()"],cwd=str(ROOT),env=env)
        with (tmp_path/'stderr.txt').open('w+',encoding='utf-8') as log:
            async with stdio_client(params,errlog=log) as (r,w):
                async with ClientSession(r,w) as session:
                    await session.initialize()
                    response=await session.call_tool('sync_conversation',{'conversation_id':'chat'})
                    result=json.loads(response.content[0].text)
            log.seek(0);diagnostic=log.read()
        assert result['error']['code']==code
        assert code in diagnostic and type_name in diagnostic
        assert 'private' not in str(result)+diagnostic
    asyncio.run(run())
