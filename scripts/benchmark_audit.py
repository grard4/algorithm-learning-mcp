"""Reproducible synthetic benchmark; tokenizer counts are not API billing."""
import argparse
import contextlib
import hashlib
import json
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from kb import KB
from context import Context
from concept_reader import ReadError,text_hash
import compact_api
import notifications
from optimized_reads import ReadCache


class TracedKB(KB):
    queries=0
    @contextlib.contextmanager
    def connect(self):
        with super().connect() as c:
            def trace(sql):
                if sql.lstrip().upper().startswith(('SELECT','PRAGMA','WITH')): self.queries+=1
            c.set_trace_callback(trace)
            yield c


def prepare(path):
    kb=TracedKB(path)
    with kb.connect() as c:
        c.execute("UPDATE r3_meta SET epoch='benchmark'")
        c.execute("INSERT INTO topics VALUES('t','Synthetic','synthetic',NULL,'time')")
        c.execute("INSERT INTO conversations VALUES('chat','t','Synthetic','','','time')")
        progress={'stage':'synthetic','mastery':'unknown','evidence':['msg'],
            'taught':['needle '+str(i) for i in range(200)],'practiced':[],'understood':[],
            'mastered':[],'pending':[]}
        c.execute('INSERT INTO topic_progress VALUES(?,?,?,?)',('t',1,json.dumps(progress),'time'))
        c.execute("INSERT INTO archives VALUES('archive','chat','synthetic','synthetic',1,'time')")
        c.execute("INSERT INTO messages VALUES('msg','chat',1,'user','time','proof','archive',1)")
        data=json.dumps({'title':'needle','content':'needle '+('synthetic long explanation. '*300),
                         'evidence':['msg'],'source_conversation':'chat'})
        c.executemany('INSERT INTO knowledge_items VALUES(?,?,?,?,?)',[(f'k{i:04}','t',1,data,'time') for i in range(500)])
        proof={'source':{'knowledge_id':'k0000','knowledge_version':1,'knowledge_data_sha256':text_hash(data),
            'source_conversation':'chat','topic_id':'t','evidence':[dict(message_id='msg',archive_sha256='archive',
                content_sha256=text_hash('proof'),locator=1,role='user',seq=1,conversation_id='chat')]}}
        c.execute("INSERT INTO c_concepts VALUES('c','needle','Needle','time')")
        c.execute("INSERT INTO c_requests VALUES('r','hash','test','time','{}')")
        c.execute("INSERT INTO c_events(concept_id,version,request_id,kind,data,topic_id,conversation_id,knowledge_id,created_at) VALUES('c',1,'r','link',?,'t','chat','k0000','time')",(json.dumps(proof),))
    return kb,Context(kb)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--label',required=True)
    args=parser.parse_args()
    try:
        import tiktoken
        encoder=tiktoken.get_encoding('cl100k_base')
    except (ImportError,OSError) as exc:
        raise SystemExit('Tokenizer unavailable; no fabricated token estimates: '+type(exc).__name__)
    def encoded(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))
    records={}
    with tempfile.TemporaryDirectory(prefix='algorithm-benchmark-') as temp:
        kb,ctx=prepare(Path(temp)/'bench.sqlite3')
        cache=ReadCache(compact_api.search,notifications.health,ReadError,'benchmark')
        def concept(cached):
            with kb.connect() as c:
                c.execute('PRAGMA query_only=ON');c.execute('BEGIN')
                if not cached: notifications.health(c)
                return (cache.query if cached else compact_api.search)(c,['needle'])
        def measure(name,payload,fn,n=10):
            timings=[];results=[];kb.queries=0
            for _ in range(n):
                start=time.perf_counter();result=fn();timings.append((time.perf_counter()-start)*1000)
                results.append(encoded(result))
            assert len(set(results))==1,'unstable result'
            records[name]={'requests':n,'input_tokens':len(encoder.encode(encoded(payload)))*n,
                'output_tokens':sum(len(encoder.encode(x)) for x in results),'sql_queries':kb.queries,
                'median_ms':round(statistics.median(timings),3),'result_sha256':hashlib.sha256(results[0].encode()).hexdigest(),
                'coverage':result.get('coverage','not_applicable')}
        measure('batch_progress',{'concepts':['needle'],'detail':'detailed'},lambda:ctx.search(concepts=['needle'],detail='detailed'))
        measure('concept_uncached',{'concepts':['needle']},lambda:concept(False),20)
        measure('concept_cached',{'concepts':['needle']},lambda:concept(True),20)
        assert records['concept_uncached']['result_sha256']==records['concept_cached']['result_sha256']
        records['concept_cached'].update(cache_hits=cache.hits,cache_misses=cache.misses)
        measure('L0_version',{'topic_id':'t'},lambda:ctx.version('t'))
        measure('L1_summary',{'topic_id':'t'},lambda:ctx.topic('t'))
        measure('L1_full',{'topic_id':'t','full':True},lambda:ctx.topic('t',full=True))
        measure('L2_search',{'query':'needle'},lambda:ctx.search(query='needle'))
        measure('L3_chunk',{'knowledge_id':'k0000','chars':1000},lambda:ctx.read('k0000',chars=1000))
        measure('unchanged',{'topic_id':'t','known_version':0},lambda:ctx.topic('t',known_version=0))
        assert kb.rows('PRAGMA integrity_check')[0]['integrity_check']=='ok'
        assert kb.rows('PRAGMA foreign_key_check')==[]
    output={'label':args.label,'tokenizer':'cl100k_base','token_scope':'serialized request arguments and tool results only; not actual API billing',
            'dataset':{'knowledge_items':500,'progress_entries':200,'approved_links':1},'results':records}
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(output,ensure_ascii=True))


if __name__=='__main__':main()
