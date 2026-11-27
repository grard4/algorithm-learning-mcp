"""只读适配本机 Codex rollout；格式变化时停止该文件并记录错误。"""
import argparse, hashlib, json, os, re, time
from pathlib import Path
import zstandard
from kb import KB, KBError, ROOT, digest, dump, now, uid
from archive_io import archive_path, publish

def discovery_cutoff():
    """Persist a one-time discovery boundary so watch mode does not reset per poll."""
    path=ROOT/'config'/'discovery_since.txt'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open('x', encoding='utf-8') as f:
            f.write(str(time.time()))
    except FileExistsError:
        pass
    try:
        value=float(path.read_text(encoding='utf-8').strip())
    except (OSError, ValueError) as exc:
        raise KBError('INVALID_DISCOVERY_CUTOFF', 'config/discovery_since.txt must contain a Unix timestamp') from exc
    if value < 0:
        raise KBError('INVALID_DISCOVERY_CUTOFF', 'discovery cutoff cannot be negative')
    return value


def configured_aliases():
    path=ROOT/'config'/'topic_aliases.json'
    if not path.exists(): return []
    try: data=json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError): return []
    rows=data.get('aliases',[]) if isinstance(data,dict) else []
    return [row for row in rows if isinstance(row,dict) and isinstance(row.get('name'),str) and isinstance(row.get('canonical'),str) and isinstance(row.get('aliases',[]),list)]
_scanned={}
def read_bytes(path):
    raw=Path(path).read_bytes()
    if str(path).endswith('.zst'):
        parts=[]
        try:
            while raw:
                decoder=zstandard.ZstdDecompressor().decompressobj()
                parts.append(decoder.decompress(raw))
                if not decoder.eof:
                    raise KBError('INVALID_LOG', '压缩日志帧不完整')
                raw=decoder.unused_data
        except zstandard.ZstdError as exc:
            raise KBError('INVALID_LOG', '压缩日志损坏') from exc
        return b''.join(parts)
    return raw
def parse(raw):
    lines=raw.splitlines(keepends=True); events=[]
    for i,line in enumerate(lines,1):
        try: e=json.loads(line)
        except (ValueError,UnicodeDecodeError):
            if i==len(lines) and not line.endswith(b'\n'):
                raise KBError('INCOMPLETE_LOG', '尾行尚未完成，请稍后重试')
            raise KBError('INVALID_LOG',f'第 {i} 行无效')
        if not isinstance(e, dict) or not isinstance(e.get('payload'), dict):
            raise KBError('INVALID_LOG', f'第 {i} 行事件结构无效')
        events.append((i,e))
    if not events or events[0][1].get('type')!='session_meta': raise KBError('INVALID_LOG','缺少 session_meta')
    return events
def visible(events):
    out=[]
    for line,e in events:
        p=e.get('payload',{})
        if e.get('type')=='response_item' and p.get('type')=='message' and p.get('role') in ('user','assistant'):
            content=p.get('content',[])
            if (not isinstance(content,list) or any(not isinstance(x,dict) or
                ('text' in x and not isinstance(x['text'],str)) for x in content)):
                raise KBError('INVALID_LOG',f'第 {line} 行消息内容结构无效')
            text='\n'.join(x.get('text','') for x in content if x.get('type') in ('input_text','output_text','text'))
            if text: out.append(dict(seq=line,role=p['role'],timestamp=e.get('timestamp'),content=text,source_line=line))
    return out
def intent(messages):
    # 只读取用户明确的长期课程请求；混合领域留给代理确认。
    for m in messages:
        s=m['content']
        if m['role']!='user' or len(s)>16000 or 'AGENTS.md instructions' in s or 'environment_context' in s: continue
        if not re.search(r'(系统.{0,8}(学习|讲解)|完整.{0,8}知识体系|长期.{0,8}(学习|训练))',s): continue
        lead=s[:1600]
        if not re.search(r'算法竞赛|ICPC|CCPC|数据结构',lead,re.I): continue
        hits=[]
        for item in configured_aliases():
            terms=[item['name'],item['canonical'],*item.get('aliases',[])]
            if any(isinstance(term,str) and term and term.casefold() in lead.casefold() for term in terms):
                hits.append((item['name'],item['canonical']))
        first=lead.split('\n\n')[0]
        primary=[pair for pair in hits if pair[0].casefold() in first.casefold() or pair[1].casefold() in first.casefold()]
        if len(set(primary))==1: return primary[0]
        if len(set(hits))==1: return hits[0]
        # No publisher-specific topic catalogue: unresolved discovery remains pending.
        return ('ambiguous','ambiguous')
    return None
def candidates(kb,tid,cid,new_messages):
    for m in new_messages:
        s=m['content']
        if m['role']!='assistant' or len(s)<300 or not re.search(r'第.{1,8}课|结论|定理|复杂度|正确性|课程正文|知识点|学习进度',s): continue
        # 原文候选不声称定理正确或学生已掌握。
        heading=next((x.strip('# *') for x in s.splitlines() if x.strip()),'课程记录')[:160]
        ident=digest([cid,m['seq'],'excerpt'])
        tags=[tag for tag in ('分治','树状数组','扫描线','二分图','模运算','线性空间','动态规划','不变量','反例','卷积') if tag in s]
        # Bounded verbatim excerpt, NOT a generated semantic summary. Full proof remains in messages.
        excerpt=s[:900]
        data={'title':heading,'content':excerpt,'content_hash':digest(excerpt.strip()),'excerpt_only':len(s)>900,'status':'candidate','evidence_level':'assistant_statement','source_conversation':cid,'evidence':[m['id']],'tags':tags}
        same=kb.rows("SELECT id,data,version FROM knowledge_items WHERE topic_id=? AND json_extract(data,'$.content_hash')=?",(tid,data['content_hash']))
        if same:
            old=same[0];merged=json.loads(old['data'])
            if m['id'] not in merged.get('evidence',[]):
                merged['evidence']=list(dict.fromkeys(merged.get('evidence',[])+[m['id']]))
                kb.write('knowledge_items',old['id'],merged,'extract:'+ident,'local-extractor',cid,old['version'])
            continue
        kb.write('knowledge_items',ident,data,'extract:'+ident,'local-extractor',cid,topic_id=tid)
        for tag in tags:
            related=kb.search(tag,limit=10)
            for other in [x for x in related if x['topic_id']!=tid and tag in x['data'].get('tags',[])][:2]:
                a,b=sorted([ident,other['id']]);rid=digest([a,b,'candidate-related'])
                if not kb.rows('SELECT id FROM knowledge_relations WHERE id=?',(rid,)):
                    kb.write('knowledge_relations',rid,{'reason':'共享术语：'+tag,'status':'candidate','verification':'词汇关联，不代表证明或已掌握'},'auto-rel:'+rid,'local-extractor',cid,extra={'source_id':a,'target_id':b,'kind':'candidate-related'})
def finish_extraction(kb,tid,cid):
    for m in kb.rows("SELECT m.* FROM messages m LEFT JOIN extraction_seen e ON e.message_id=m.id WHERE m.conversation_id=? AND m.role='assistant' AND m.seq>0 AND e.message_id IS NULL",(cid,)):
        ident=digest([cid,m['seq'],'excerpt'])
        if not kb.rows('SELECT id FROM updates WHERE request_id=?',('extract:'+ident,)): candidates(kb,tid,cid,[m])
        with kb.connect() as c:
            c.execute('INSERT OR IGNORE INTO extraction_seen VALUES(?,?)',(m['id'],now()))
def sync_file(kb,path,title=None,name=None,canonical=None,allow_new=False):
    raw=read_bytes(path); events=parse(raw); meta=events[0][1]['payload']; cid=meta.get('id'); messages=visible(events)
    sha=digest(raw)
    archive=archive_path(kb,cid,sha,'.jsonl')
    known=kb.rows('SELECT * FROM conversations WHERE id=?',(cid,))
    if not known:
        if not name:
            found=intent(messages) if allow_new else None
            if not found: return {'ignored':cid}
            name,canonical=found
            if canonical=='ambiguous':
                with kb.connect() as c: c.execute('INSERT OR REPLACE INTO discovery_candidates VALUES(?,?,?,?)',(cid,str(path),'多个领域或课程范围不明确，需课程代理确认',now()))
                return {'candidate':cid}
            name+='算法学习'
        reg=kb.register(name,canonical,cid,title or name,meta.get('cwd',''),str(path)); tid=reg['topic_id']
    else:
        tid=known[0]['topic_id']
    state=kb.rows('SELECT * FROM sync_state WHERE conversation_id=?',(cid,))
    if state and state[0]['source_hash']==sha:
        finish_extraction(kb,tid,cid)
        return {'conversation_id':cid,'unchanged':True}
    # 内容寻址归档只创建一次，重试验证内容而非覆盖。
    publish(archive,raw)
    fresh=[]
    def fn(c,u):
        previous=c.execute('SELECT line_count FROM sync_state WHERE conversation_id=?',(cid,)).fetchone()
        if previous and previous['line_count']>len(events):
            raise KBError('SOURCE_TRUNCATED','源日志行数减少，停止推进游标')
        c.execute('INSERT OR IGNORE INTO archives VALUES(?,?,?,?,?,?)',(sha,cid,str(archive),str(path),len(raw),now()))
        for m in messages:
            m['id']=digest([cid,m['seq']]); m['conversation_id']=cid; m['source_hash']=sha
            old=c.execute('SELECT * FROM messages WHERE id=?',(m['id'],)).fetchone()
            if old:
                fields=('id','conversation_id','seq','role','timestamp','content','source_line')
                if any(old[key]!=m[key] for key in fields): raise KBError('SOURCE_CHANGED','已有消息元数据或正文被改写，保留原档并停止导入')
            else:
                c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)',tuple(m[k] for k in ('id','conversation_id','seq','role','timestamp','content','source_hash','source_line'))); fresh.append(m)
        prior_count=c.execute('SELECT count(*) FROM messages WHERE conversation_id=? AND seq>0',(cid,)).fetchone()[0]
        if prior_count>len(messages): raise KBError('SOURCE_TRUNCATED','源文件缩短，停止推进游标')
        conv=dict(c.execute('SELECT * FROM conversations WHERE id=?',(cid,)).fetchone())
        if conv['source_path']!=str(path):
            conv['source_path']=str(path)
            kb.change(c,u,'conversations',cid,conv)
        c.execute('INSERT OR REPLACE INTO sync_state VALUES(?,?,?,?,NULL)',(cid,sha,len(events),now()))
        return {'conversation_id':cid,'imported':len(fresh),'archive_sha256':sha,'messages':len(messages)}
    result=kb.mutate('sync','sync:'+cid+':'+sha,'local-sync',cid,[sha],fn)
    # 即使上次在归档后中断，重新运行仍补齐提取；每条候选有稳定幂等键。
    finish_extraction(kb,tid,cid)
    return result
def sources(home):
    return [p for folder in ('sessions','archived_sessions') for p in (home/folder).rglob('rollout-*.jsonl*') if p.suffix in ('.jsonl','.zst')]
def report(kb):
    out=kb.path.parent/'reports'; out.mkdir(exist_ok=True)
    fingerprint=digest([kb.rows('SELECT MAX(change_id) v FROM context_events'),kb.rows('SELECT MAX(rowid) v FROM archives'),now()[:10]])
    stamp=out/'report.version'
    if stamp.exists() and stamp.read_text(encoding='utf-8')==fingerprint:return
    overview=kb.overview(); (out/'overview.json').write_text(json.dumps(overview,ensure_ascii=False,indent=2),encoding='utf-8')
    rows=['# 算法竞赛学习','',f'生成时间：{now()}（UTC）','', '逻辑会话树；原始聊天保持独立。','']
    for t in overview['topics']:
        p=t['progress']; rows.extend([f'## {t["name"]}','',f'阶段：{p.get("stage","未知")}','',f'掌握证据：{p.get("mastery","未知")}','',f'已讲解：{p.get("taught",[])}','',f'待学习：{p.get("pending",[])}',''])
    (out/'overview.md').write_text('\n'.join(rows),encoding='utf-8')
    daily=out/(now()[:10]+'.json')
    if not daily.exists():daily.write_text(json.dumps(overview,ensure_ascii=False,indent=2),encoding='utf-8')
    backup=kb.path.parent/'backups'/(now()[:10]+'.sqlite3')
    if not backup.exists():kb.backup(backup)
    stamp.write_text(fingerprint,encoding='utf-8')
def run(kb,home,discover=False,initial=False):
    paths=sources(home); results=[]
    initial_rows=json.loads((ROOT/'config'/'initial_threads.json').read_text(encoding='utf-8')) if initial else []
    cutoff=discovery_cutoff() if discover else None
    for t in initial_rows:
        matches=[p for p in paths if t['id'] in p.name]
        if len(matches)!=1: raise KBError('SOURCE_AMBIGUOUS',t['id'])
        name=t.get('name') or t['title']
        results.append(sync_file(kb,matches[0],t['title'],name,t.get('canonical')))
    known={r['id'] for r in kb.rows('SELECT id FROM conversations')}
    for p in paths:
        # 未来发现只处理系统安装之后的新文件；不扩大到其他历史聊天。
        is_known=any(cid in p.name for cid in known)
        if not is_known and (not discover or p.stat().st_ctime<cutoff): continue
        try:
            stat=p.stat(); signature=(stat.st_size,stat.st_mtime_ns)
            if _scanned.get(str(p))==signature:continue
            result=sync_file(kb,p,allow_new=discover)
            results.append(result)
            _scanned[str(p)]=signature
        except Exception as e: results.append({'source':str(p),'error':str(e)})
    report(kb); return results
def acquire_worker_lock(path):
    """One worker per database, using the platform's native advisory lock."""
    lock=Path(path).open('a+b')
    try:
        if os.name=='nt':
            import msvcrt
            if lock.seek(0,os.SEEK_END)==0:
                lock.write(b'0');lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except OSError as exc:
        lock.close()
        import errno
        if exc.errno in (errno.EACCES,errno.EAGAIN,errno.EDEADLK):
            return None
        raise
    return lock


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--home',default=str(Path.home()/'.codex')); ap.add_argument('--initial',action='store_true'); ap.add_argument('--discover',action='store_true'); ap.add_argument('--watch',action='store_true'); ap.add_argument('--interval',type=int,default=120); a=ap.parse_args(); kb=KB()
    lock=None
    if a.watch:
        lock=acquire_worker_lock(kb.path.parent/'worker.lock')
        if lock is None:raise KBError('WORKER_RUNNING','已有同步进程持有数据库工作锁')
    while True:
        try:
            result=run(kb,Path(a.home),a.discover,a.initial)
            log=kb.path.parent/'sync.jsonl'
            with log.open('a',encoding='utf-8') as f: f.write(dump({'time':now(),'results':result})+'\n')
            if not a.watch: print(dump(result))
        except Exception as e:
            with (kb.path.parent/'sync.jsonl').open('a',encoding='utf-8') as f: f.write(dump({'time':now(),'error':str(e)})+'\n')
            if not a.watch: raise
        if not a.watch: break
        a.initial=False; time.sleep(max(30,a.interval))
if __name__=='__main__': main()
