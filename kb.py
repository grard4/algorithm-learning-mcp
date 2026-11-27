from __future__ import annotations
import contextlib, hashlib, json, os, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
def now(): return datetime.now(timezone.utc).isoformat()
def dump(x): return json.dumps(x, ensure_ascii=False, sort_keys=True)
def uid(): return str(uuid.uuid4())
def digest(x): return hashlib.sha256(x if isinstance(x, bytes) else dump(x).encode()).hexdigest()

class KBError(Exception):
    def __init__(self, code, message, details=None):
        self.code, self.message, self.details = code, message, details
        super().__init__(message)

class KB:
    def __init__(self, path=None, initialize=True):
        self.path = Path(path or os.environ.get('ALGORITHM_KB', ROOT/'data'/'learning.sqlite3'))
        if not initialize:
            with contextlib.closing(sqlite3.connect(self.path.absolute().as_uri()+'?mode=ro',uri=True)) as check:
                check.execute('PRAGMA query_only=ON')
                check.execute('SELECT id FROM topics LIMIT 1')
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.execute('PRAGMA journal_mode=WAL')
            from migrations import initialize
            initialize(c, ROOT)
    @contextlib.contextmanager
    def connect(self):
        c=sqlite3.connect(self.path, timeout=30); c.row_factory=sqlite3.Row
        c.execute('PRAGMA foreign_keys=ON'); c.execute('PRAGMA busy_timeout=30000')
        try: yield c; c.commit()
        except: c.rollback(); raise
        finally: c.close()
    def rows(self, sql, args=()):
        with self.connect() as c: return [dict(x) for x in c.execute(sql,args)]
    def get(self, table, ident):
        if table not in {'topic_progress','knowledge_items','learning_tasks','knowledge_relations'}: raise KBError('INVALID','非法实体')
        r=self.rows(f'SELECT * FROM {table} WHERE id=?',(ident,))
        if not r: raise KBError('NOT_FOUND',ident)
        r=r[0]; r['data']=json.loads(r['data']); return r
    def mutate(self, operation, request_id, actor, conversation_id, payload, fn):
        if not request_id or not actor: raise KBError('INVALID','需要 request_id 和 actor')
        h=digest([operation,actor,conversation_id,payload])
        with self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            old=c.execute('SELECT * FROM updates WHERE request_id=?',(request_id,)).fetchone()
            if old:
                if old['request_hash']!=h: raise KBError('IDEMPOTENCY_CONFLICT','同一 request_id 的内容不同')
                return json.loads(old['result'])
            update_id=uid()
            c.execute('INSERT INTO updates VALUES(?,?,?,?,?,?,?,?)',(update_id,request_id,h,actor,conversation_id,operation,now(),'{}'))
            result=fn(c,update_id); result['update_id']=update_id
            c.execute('UPDATE updates SET result=? WHERE id=?',(dump(result),update_id))
            return result
    def change(self,c,u,table,ident,after):
        old=c.execute(f'SELECT * FROM {table} WHERE id=?',(ident,)).fetchone()
        before=dict(old) if old else None
        if after is None: c.execute(f'DELETE FROM {table} WHERE id=?',(ident,))
        elif old:
            cols=[k for k in after if k!='id']
            c.execute(f'UPDATE {table} SET '+','.join(k+'=?' for k in cols)+' WHERE id=?',tuple(after[k] for k in cols)+(ident,))
        else:
            c.execute(f'INSERT INTO {table} ('+','.join(after)+') VALUES('+','.join('?' for _ in after)+')',tuple(after.values()))
        c.execute('INSERT INTO change_history(update_id,entity,entity_id,before_json,after_json) VALUES(?,?,?,?,?)',(u,table,ident,dump(before) if before else None,dump(after) if after else None))
    def register(self, name, canonical, conversation_id, title, cwd='', source_path='', parent_id=None):
        # 规范名由确认过的课程意图提供，避免按标题相似度合并。
        from topic_identity import resolve
        canonical=canonical.strip().lower()
        if not name or not conversation_id: raise KBError('INVALID','专题名和聊天标识不能为空')
        def fn(c,u):
            old=c.execute('SELECT * FROM conversations WHERE id=?',(conversation_id,)).fetchone()
            t,resolved=resolve(c,name,canonical)
            if t and parent_id is not None and t['parent_id'] != parent_id:
                raise KBError('TOPIC_CONFLICT','已有专题的父节点不同；进阶分支须使用明确的新名称')
            if parent_id and not c.execute('SELECT id FROM topics WHERE id=?',(parent_id,)).fetchone():
                raise KBError('NOT_FOUND','父专题不存在')
            if old:
                if not t or old['topic_id']!=t['id']: raise KBError('TOPIC_CONFLICT','已有聊天不能自动改归属')
                return {'topic_id':t['id'],'conversation_id':conversation_id}
            tid=t['id'] if t else uid()
            if not t:
                self.change(c,u,'topics',tid,dict(id=tid,name=name,canonical=resolved,parent_id=parent_id,created_at=now()))
                node='topic:'+tid
                self.change(c,u,'conversation_tree',node,dict(id=node,parent_id='topic:'+parent_id if parent_id else 'root',topic_id=tid,conversation_id=None,label=name))
                self.change(c,u,'topic_progress',tid,dict(id=tid,version=1,data=dump({'stage':'未知','taught':[],'practiced':[],'understood':[],'mastered':[],'pending':[],'completed_exercises':[],'pending_exercises':[],'conclusions':[],'common_errors':[],'mastery':'未知','evidence':[]}),updated_at=now()))
            self.change(c,u,'conversations',conversation_id,dict(id=conversation_id,topic_id=tid,title=title,cwd=cwd,source_path=source_path,created_at=now()))
            node='chat:'+conversation_id
            self.change(c,u,'conversation_tree',node,dict(id=node,parent_id='topic:'+tid,topic_id=tid,conversation_id=conversation_id,label=title))
            return {'topic_id':tid,'conversation_id':conversation_id}
        return self.mutate('register','register:'+conversation_id,'registration',None,[name,canonical,conversation_id,title,cwd,source_path,parent_id],fn)
    def write(self,table,ident,data,request_id,actor,conversation_id=None,expected_version=None,topic_id=None,extra=None):
        if table not in {'topic_progress','knowledge_items','learning_tasks','knowledge_relations'}: raise KBError('INVALID','非法实体')
        def fn(c,u):
            old=c.execute(f'SELECT * FROM {table} WHERE id=?',(ident,)).fetchone()
            if old and (expected_version is None or old['version']!=expected_version): raise KBError('VERSION_CONFLICT',f'当前版本 {old["version"]}；请重新读取后更新')
            if not old and expected_version not in (None,0): raise KBError('VERSION_CONFLICT','实体尚不存在')
            if old and json.loads(old['data'])==data:
                return {'id':ident,'version':old['version'],'unchanged':True}
            row=dict(old) if old else dict(id=ident,**({'topic_id':topic_id} if table in {'knowledge_items','learning_tasks'} else {}),**(extra or {}))
            row.update(data=dump(data),version=old['version']+1 if old else 1,updated_at=now())
            self.change(c,u,table,ident,row)
            return {'id':ident,'version':row['version']}
        return self.mutate('write:'+table,request_id,actor,conversation_id,[ident,data,expected_version,topic_id,extra],fn)
    def rollback(self,update_id,request_id,actor):
        def fn(c,u):
            changes=c.execute('SELECT * FROM change_history WHERE update_id=? ORDER BY id DESC',(update_id,)).fetchall()
            if not changes: raise KBError('NOT_ROLLBACKABLE','没有可回滚的结构化变更；原始归档保留')
            for ch in changes:
                if ch['entity'] not in {'topic_progress','knowledge_items','learning_tasks','knowledge_relations'}: raise KBError('NOT_ROLLBACKABLE','注册和原始历史不可回滚删除')
                current=c.execute(f'SELECT * FROM {ch["entity"]} WHERE id=?',(ch['entity_id'],)).fetchone()
                if (dump(dict(current)) if current else None)!=ch['after_json']: raise KBError('ROLLBACK_CONFLICT','实体后来已更新，请先处理后续版本')
                before=json.loads(ch['before_json']) if ch['before_json'] else None
                if before and current: before.update(version=current['version']+1,updated_at=now())
                self.change(c,u,ch['entity'],ch['entity_id'],before)
            return {'rolled_back':update_id,'count':len(changes)}
        return self.mutate('rollback',request_id,actor,None,[update_id],fn)
    def progress(self,topic_id): return self.get('topic_progress',topic_id)
    def topics(self): return self.rows('SELECT t.*,p.version,p.updated_at,json_extract(p.data,\'$.stage\') stage,json_extract(p.data,\'$.mastery\') mastery FROM topics t JOIN topic_progress p ON p.id=t.id ORDER BY t.created_at')
    def overview(self): return {'root':'算法竞赛学习','topics':[dict(t,progress=self.progress(t['id'])['data']) for t in self.topics()], 'generated_at':now(),'unreviewed_count':self.rows("SELECT count(*) n FROM knowledge_items WHERE json_extract(data,'$.status')='candidate'")[0]['n']}
    def search(self,query,topic_id=None,limit=20,since=None,conversation_id=None):
        if not query.strip(): raise KBError('INVALID','查询不能为空')
        limit=max(1,min(limit,100))
        # trigram 支持中文连续子串；短于三个字符时使用转义 LIKE。
        args=[]
        if len(query)>=3:
            sql='SELECT k.* FROM knowledge_items k JOIN knowledge_fts f ON f.id=k.id WHERE knowledge_fts MATCH ?'; args=['"'+query.replace('"','""')+'"']
        else:
            sql="SELECT k.* FROM knowledge_items k WHERE k.data LIKE ? ESCAPE '\\'"; args=['%'+query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%']
        if topic_id: sql+=' AND k.topic_id=?'; args.append(topic_id)
        if since: sql+=' AND k.updated_at>=?'; args.append(since)
        if conversation_id: sql+=" AND json_extract(k.data,'$.source_conversation')=?"; args.append(conversation_id)
        sql+=' ORDER BY k.updated_at DESC LIMIT ?'; args.append(limit)
        return [dict(r,data=json.loads(r['data'])) for r in self.rows(sql,args)]
    def conflicts(self):
        items=self.rows('SELECT id,topic_id,data FROM knowledge_items'); groups={}
        for r in items:
            d=json.loads(r['data']); key=d.get('claim_key')
            if key: groups.setdefault(key,[]).append(dict(id=r['id'],topic_id=r['topic_id'],claim_value=d.get('claim_value'),status=d.get('status'),evidence=d.get('evidence',[])))
        return {'method':'同 claim_key 不同 claim_value 的候选冲突；自然语言矛盾由课程代理复核','conflicts':[{'claim_key':k,'versions':v} for k,v in groups.items() if len({dump(x['claim_value']) for x in v})>1]}
    def backup(self,path):
        target=Path(path)
        if target.exists(): raise KBError('EXISTS','备份目标已存在')
        target.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as src, contextlib.closing(sqlite3.connect(target)) as dst: src.backup(dst)
        return str(target)
