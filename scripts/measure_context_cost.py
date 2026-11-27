"""Measure actual stdio initialization and tools/list; optional tiktoken required."""
import argparse
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
import tiktoken


async def measure(repo):
    with tempfile.TemporaryDirectory(prefix='algorithm-cost-') as temp:
        params=StdioServerParameters(command=sys.executable,args=[str(repo/'server.py')],cwd=str(repo),
            env={'ALGORITHM_KB':str(Path(temp)/'synthetic.sqlite3'),
                 'ALGORITHM_PREFERENCES':str(Path(temp)/'missing'),'ALGORITHM_LEGACY_TOOLS':'0'})
        async with stdio_client(params) as (r,w):
            async with ClientSession(r,w) as session:
                init=await session.initialize();listed=await session.list_tools()
                encode=lambda value:json.dumps(value,ensure_ascii=False,separators=(',',':'))
                texts={'instructions':init.instructions or '',
                    'tools_list':encode([t.model_dump(mode='json',exclude_none=True) for t in listed.tools]),
                    'input_schemas':encode([t.inputSchema for t in listed.tools])}
                return {'commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip(),
                    'tree':subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=repo,text=True).strip(),
                    'tool_count':len(listed.tools),'transport':'stdio Python SDK',
                    'measurements':{name:{'utf8_bytes':len(text.encode()),
                        **{enc:len(tiktoken.get_encoding(enc).encode(text)) for enc in ('cl100k_base','o200k_base')}} for name,text in texts.items()},
                    'actual_client_billing':'NOT VERIFIED; excludes client framing/caching/model-specific processing'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[1]);parser.add_argument('--output',type=Path)
    args=parser.parse_args();result=asyncio.run(measure(args.repo.resolve()))
    text=json.dumps(result,indent=2)+'\n'
    if args.output:args.output.write_text(text,encoding='utf-8')
    print(text)
