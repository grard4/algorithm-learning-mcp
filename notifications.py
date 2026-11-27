"""Isolated transactional invalidation journal. Never approves concept links."""
import base64
import hashlib
import json
import pathlib
import sqlite3
import uuid

ROOT=pathlib.Path(__file__).resolve().parent
RULE='c23-invalidation-r3-v1'
SOURCES={'knowledge_items':'id','messages':'id','archives':'sha256','conversations':'id','topics':'id'}

class NoticeError(ValueError):
    def __init__(self,code):self.code=code;super().__init__(code)

def need(value,code):
    if not value:raise NoticeError(code)

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def checked_path(path):
    from sandbox import checked
    return checked(path)


def q(name):return '"'+name.replace('"','""')+'"'

def schema_hash(c):
    return digest([tuple(r) for r in c.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE substr(name,1,3)='r3_' ORDER BY name")])

def source_schema_hash(c):
    names=[*SOURCES,'c_concepts','c_events']
    return digest([tuple(r) for r in c.execute('SELECT name,sql FROM sqlite_master WHERE type=\'table\' AND name IN ('+','.join('?' for _ in names)+') ORDER BY name',names)])

def health(c):
    try:m=c.execute('SELECT * FROM r3_meta WHERE singleton=1').fetchone()
    except sqlite3.OperationalError as ex:raise NoticeError('NOT_INSTALLED') from ex
    need(m is not None and m['rule']==RULE,'JOURNAL_VERSION_MISMATCH')
    need(m['schema_hash']==schema_hash(c) and m['source_schema_hash']==source_schema_hash(c),'JOURNAL_SCHEMA_CHANGED')
    return m

def dep_insert(where):
    # Frozen proofs, not mutable FK fields, keep dependencies through delete/recreate.
    pieces=[]
    for table,path in [('knowledge_items','$.source.knowledge_id'),('topics','$.source.topic_id'),('conversations','$.source.source_conversation')]:
        pieces.append(f"SELECT e.seq,e.concept_id,'{table}',json_extract(e.data,'{path}') FROM c_events e WHERE {where} AND e.kind='link' AND json_type(e.data,'{path}')='text'")
    for table,field in [('messages','message_id'),('archives','archive_sha256')]:
        obj="CASE WHEN j.type='object' THEN j.value ELSE '{}' END"
        pieces.append(f"SELECT e.seq,e.concept_id,'{table}',json_extract({obj},'$.{field}') FROM c_events e,json_each(e.data,'$.source.evidence') j WHERE {where} AND e.kind='link' AND json_type({obj},'$.{field}')='text'")
    return 'INSERT OR IGNORE INTO r3_dependencies(event_seq,concept_id,source_table,source_key) '+' UNION '.join(pieces)+';'

def enqueue(select,table,key,op):
    return f"INSERT INTO r3_notices(concept_id,source_table,source_key,operation) SELECT DISTINCT concept_id,'{table}',{key},'{op}' FROM ({select});"

def install_transaction(c):
    need(c.in_transaction,'WRITE_TRANSACTION_REQUIRED')
    if c.execute("SELECT 1 FROM sqlite_master WHERE name='r3_meta'").fetchone():
        return {'installed':False,'epoch':health(c)['epoch']}
    need(not c.execute("SELECT 1 FROM sqlite_master WHERE substr(name,1,3)='r3_'").fetchone(),'PARTIAL_INSTALL')
    c.execute('CREATE TABLE r3_meta(singleton INTEGER PRIMARY KEY CHECK(singleton=1),rule TEXT NOT NULL,epoch TEXT NOT NULL,schema_hash TEXT NOT NULL,source_schema_hash TEXT NOT NULL)')
    c.execute('CREATE TABLE r3_dependencies(event_seq INTEGER NOT NULL,concept_id TEXT NOT NULL,source_table TEXT NOT NULL,source_key TEXT NOT NULL,PRIMARY KEY(event_seq,source_table,source_key))')
    c.execute('CREATE INDEX r3_dependency_source ON r3_dependencies(source_table,source_key,concept_id)')
    c.execute("CREATE TABLE r3_notices(seq INTEGER PRIMARY KEY AUTOINCREMENT,concept_id TEXT NOT NULL,source_table TEXT NOT NULL,source_key TEXT NOT NULL,operation TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')))")
    for op in ['UPDATE','DELETE']:
        c.execute(f"CREATE TRIGGER r3_notice_no_{op.lower()} BEFORE {op} ON r3_notices BEGIN SELECT RAISE(ABORT,'R3_APPEND_ONLY'); END")
    c.execute(dep_insert('1=1'))
    for table,key in SOURCES.items():
        columns=[r['name'] for r in c.execute('PRAGMA table_info('+q(table)+')')]
        changed=' OR '.join(f'OLD.{q(col)} IS NOT NEW.{q(col)}' for col in columns)
        for op in ['INSERT','UPDATE','DELETE']:
            refs=['NEW'] if op=='INSERT' else ['OLD'] if op=='DELETE' else ['OLD','NEW']
            keys=','.join(f'{ref}.{q(key)}' for ref in refs)
            select=f"SELECT concept_id FROM r3_dependencies WHERE source_table='{table}' AND source_key IN ({keys})"
            stamp=f"{refs[0]}.{q(key)}"
            when=' WHEN '+changed if op=='UPDATE' else ''
            timing='BEFORE' if op=='DELETE' else 'AFTER'
            c.execute(f'CREATE TRIGGER r3_{table}_{op.lower()} {timing} {op} ON {q(table)}{when} BEGIN '+enqueue(select,table,stamp,op.lower())+' END')
    for table,key in [('c_events','seq'),('c_concepts','id')]:
        columns=[r['name'] for r in c.execute('PRAGMA table_info('+q(table)+')')]
        changed=' OR '.join(f'OLD.{q(col)} IS NOT NEW.{q(col)}' for col in columns)
        for op in ['INSERT','UPDATE','DELETE']:
            refs=['NEW'] if op=='INSERT' else ['OLD'] if op=='DELETE' else ['OLD','NEW']
            cid='concept_id' if table=='c_events' else 'id'
            select=' UNION '.join(f'SELECT {ref}.{cid} AS concept_id' for ref in refs)
            body=enqueue(select,table,f'CAST({refs[0]}.{key} AS TEXT)',op.lower())
            if table=='c_events':
                if op!='INSERT':body+='DELETE FROM r3_dependencies WHERE event_seq=OLD.seq;'
                if op!='DELETE':body+=dep_insert('e.seq=NEW.seq')
            when=' WHEN '+changed if op=='UPDATE' else ''
            c.execute(f'CREATE TRIGGER r3_{table}_{op.lower()} AFTER {op} ON {table}{when} BEGIN '+body+' END')
    epoch=str(uuid.uuid4())
    c.execute('INSERT INTO r3_meta VALUES(1,?,?,?,?)',(RULE,epoch,schema_hash(c),source_schema_hash(c)))
    return {'installed':True,'epoch':epoch}


def token(epoch,after,through):
    data={'v':RULE,'epoch':epoch,'after':after,'through':through}
    return base64.urlsafe_b64encode(json.dumps(data,separators=(',',':')).encode()).decode()

def changes(c,cursor=None,limit=10):
    need(c.in_transaction and c.execute('PRAGMA query_only').fetchone()[0]==1,'READ_TRANSACTION_REQUIRED')
    need(type(limit) is int and 1<=limit<=50,'INVALID_LIMIT')
    m=health(c);head=c.execute('SELECT COALESCE(MAX(seq),0) FROM r3_notices').fetchone()[0]
    if cursor is None:
        return {'rule':RULE,'bootstrap_required':True,'changes':[], 'cursor':token(m['epoch'],head,None),'has_more':False}
    need(isinstance(cursor,str) and 0<len(cursor)<=1024,'INVALID_CURSOR')
    try:d=json.loads(base64.urlsafe_b64decode(cursor))
    except Exception as ex:raise NoticeError('INVALID_CURSOR') from ex
    need(isinstance(d,dict) and set(d)=={'v','epoch','after','through'} and d['v']==RULE,'CURSOR_NAMESPACE')
    need(d['epoch']==m['epoch'],'CURSOR_EPOCH_CHANGED')
    after=d['after'];through=head if d['through'] is None else d['through']
    need(type(after) is int and type(through) is int and after>=0 and through>=0,'INVALID_CURSOR')
    need(after<=head and through<=head,'CURSOR_AHEAD_OF_JOURNAL')
    need(after<=through,'INVALID_CURSOR')
    rows=c.execute('SELECT seq,concept_id FROM r3_notices WHERE seq>? AND seq<=? ORDER BY seq LIMIT ?',
                   (after,through,limit+1)).fetchall()
    more=len(rows)>limit;rows=rows[:limit];last=rows[-1]['seq'] if rows else through
    grouped={}
    for r in rows:grouped[r['concept_id']]=r['seq']
    return {'rule':RULE,'bootstrap_required':False,'changes':[{'concept_id':k,'last_notice':v,'action':'recheck'} for k,v in grouped.items()],
            'cursor':token(m['epoch'],last if more else through,through if more else None),'has_more':more}
