"""算法学习 MCP 服务；支持 stdio 与 Streamable HTTP。"""

import contextlib, functools, json, sqlite3, os

from typing import Literal

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from kb import KB, KBError, ROOT, dump, digest, now, uid

from sync import sync_file, intent

from context import Context

from mcp.types import TextContent

from contracts import LearningChanges
from preferences import read_preferences
from course_rules import COURSE_INSTRUCTIONS, read_course_rules
import compact_api, notifications
from optimized_reads import ReadCache
from archive_io import archive_path, publish
from errors import error_response
from input_limits import NormalizedMessages, normalized_raw



mcp=FastMCP('algorithm-learning', instructions=COURSE_INSTRUCTIONS); kb=KB()

context=Context(kb)
_read_cache=ReadCache(compact_api.search, notifications.health, compact_api.core.ReadError, 'open-source-release-v1')
compact_api.search=_read_cache.query

TOOLS={}
LEGACY_WRITES=frozenset({'add_knowledge', 'add_knowledge_relation', 'update_topic_progress', 'record_learning_result', 'update_knowledge', 'record_learning_task'})

PUBLIC={'register_conversation','get_topic_context','search_knowledge','read_knowledge','get_learning_preferences','get_course_rules',

        'update_learning','get_global_overview','get_context_manifest','get_context_delta','get_topic_version',

        'get_conversation_history','get_conversation_tree','rollback_update','get_update_history',

        'detect_knowledge_conflicts','sync_conversation','get_sync_health','record_conversation_update',
        'search_concept_knowledge','read_concept_link','get_concept_changes'}

def tool(fn):

    @functools.wraps(fn)

    def call(*a,**kw):

        try: return {'ok':True,'data':fn(*a,**kw)}

        except Exception as exc: return error_response(exc)

    TOOLS[fn.__name__]=call

    if fn.__name__ not in LEGACY_WRITES and (fn.__name__ in PUBLIC or os.environ.get('ALGORITHM_LEGACY_TOOLS')=='1'):

        @functools.wraps(fn)

        def transport(*a,**kw):

            return [TextContent(type='text',text=json.dumps(call(*a,**kw),ensure_ascii=False,separators=(',',':')))]

        mcp.tool(structured_output=False)(transport)

    return call

def evidence(data):

    refs=data.get('evidence',[])

    if not refs: raise KBError('EVIDENCE_REQUIRED','至少引用一条归档消息 ID')

    for ref in refs:

        if not isinstance(ref,str) or not kb.rows('SELECT id FROM messages WHERE id=?',(ref,)): raise KBError('EVIDENCE_NOT_FOUND',str(ref))



def _concept_read(fn, *args, check_health=True, **kwargs):
    uri=kb.path.resolve().as_uri()+'?mode=ro'
    with contextlib.closing(sqlite3.connect(uri,uri=True,timeout=3)) as c:
        c.row_factory=sqlite3.Row
        c.execute('PRAGMA query_only=ON')
        c.execute('BEGIN')
        try:
            if check_health:
                notifications.health(c)
            return fn(c,*args,**kwargs)
        except (notifications.NoticeError, compact_api.core.ReadError) as exc:
            raise KBError(exc.code,exc.code) from exc
        finally:
            c.rollback()

@tool

def search_concept_knowledge(concepts: list[str], limit: int=2, topic_ids: list[str]|None=None,
                             cursor: str|None=None, known_versions: dict[str,str]|None=None) -> dict:
    """Search approved concept links only; it does not infer or update learning state."""
    return _concept_read(compact_api.search,concepts,limit,topic_ids,cursor,known_versions,check_health=False)

@tool

def read_concept_link(event_seq: int) -> dict:
    """Read and revalidate one concept-link event and its source proof."""
    return _concept_read(compact_api.read_link,event_seq)

@tool

def get_concept_changes(cursor: str|None=None, limit: int=10) -> dict:
    """Read concept-source invalidations using an explicit cursor."""
    return _concept_read(notifications.changes,cursor,limit)

@tool

def get_learning_preferences() -> dict:
    """Read editable preferences, not built-in course rules; missing files use defaults."""
    return read_preferences()

@tool
def get_course_rules() -> dict:
    """Read mandatory built-in course rules; preferences cannot override or delete them."""
    return read_course_rules()

@tool

def get_global_context() -> dict:

    """读取全局进度、候选数量与最近更新；未知状态保留。"""

    return dict(kb.overview(),recent_updates=kb.rows('SELECT * FROM updates ORDER BY timestamp DESC LIMIT 10'))

@tool

def get_topic_progress(topic_id: str) -> dict:

    """读取专题档案和乐观锁 version。"""

    return kb.progress(topic_id)

@tool

def list_all_topics() -> list:

    """列出全部专题 ID、阶段、掌握证据状态。"""

    return kb.topics()

@tool

def search_knowledge_legacy(query: str, topic_id: str|None=None, limit: int=20, since: str|None=None, conversation_id: str|None=None) -> list:

    """FTS5 跨专题检索；短中文词回退子串匹配。since 使用 ISO UTC。"""

    return kb.search(query,topic_id,limit,since,conversation_id)

@tool

def get_knowledge_detail(knowledge_id: str) -> dict:

    """读取知识全文、来源和版本。"""

    return kb.get('knowledge_items',knowledge_id)

@tool

def get_related_knowledge(knowledge_id: str) -> list:

    """双向读取关联及对端知识。"""

    rows=kb.rows('SELECT * FROM knowledge_relations WHERE source_id=? OR target_id=?',(knowledge_id,knowledge_id))

    return [dict(r,related=kb.get('knowledge_items',r['target_id'] if r['source_id']==knowledge_id else r['source_id'])) for r in rows]

@tool

def get_conversation_history_legacy(conversation_id: str, after_seq: int|None=None, limit: int=30) -> dict:

    """按原始行序分页返回可见用户/助手消息，保留时间及原文。"""

    rows=kb.rows('SELECT * FROM messages WHERE conversation_id=? AND (? IS NULL OR seq>?) ORDER BY seq LIMIT ?',(conversation_id,after_seq,after_seq,max(1,min(limit,100))))

    return {'messages':rows,'next_after_seq':rows[-1]['seq'] if rows else after_seq}

@tool

def get_recent_updates(limit: int=20, since: str|None=None) -> list:

    """读取审计更新；可按 UTC 时间过滤。"""

    return kb.rows('SELECT * FROM updates WHERE timestamp>=? ORDER BY timestamp DESC LIMIT ?',(since or '',max(1,min(limit,100))))

@tool

def update_topic_progress(topic_id: str, data: dict, expected_version: int, request_id: str, conversation_id: str, actor: str='course-agent') -> dict:

    """Retired unsafe legacy write; use update_learning with topic_version and evidence."""
    raise KBError('LEGACY_WRITE_DISABLED','旧写入接口已停用；请使用 update_learning 并提供 topic_version 和证据来源')

@tool

def add_knowledge(topic_id: str, data: dict, request_id: str, conversation_id: str, actor: str='course-agent') -> dict:

    """Retired unsafe legacy write; use update_learning with topic_version and evidence."""
    raise KBError('LEGACY_WRITE_DISABLED','旧写入接口已停用；请使用 update_learning 并提供 topic_version 和证据来源')

@tool

def update_knowledge(knowledge_id: str, data: dict, expected_version: int, request_id: str, conversation_id: str, actor: str='course-agent') -> dict:

    """Retired unsafe legacy write; use update_learning with topic_version and evidence."""
    raise KBError('LEGACY_WRITE_DISABLED','旧写入接口已停用；请使用 update_learning 并提供 topic_version 和证据来源')

@tool

def add_knowledge_relation(source_id: str, target_id: str, kind: str, reason: str, request_id: str, conversation_id: str, actor: str='course-agent') -> dict:

    """Retired unsafe legacy write; use update_learning with topic_version and evidence."""
    raise KBError('LEGACY_WRITE_DISABLED','旧写入接口已停用；请使用 update_learning 并提供 topic_version 和证据来源')

@tool

def record_learning_task(topic_id: str, data: dict, request_id: str, conversation_id: str, actor: str='course-agent') -> dict:

    """Retired unsafe legacy write; use update_learning with topic_version and evidence."""
    raise KBError('LEGACY_WRITE_DISABLED','旧写入接口已停用；请使用 update_learning 并提供 topic_version 和证据来源')

@tool

def record_learning_result(task_id: str, data: dict, expected_version: int, request_id: str, conversation_id: str, actor: str='course-agent') -> dict:

    """Retired unsafe legacy write; use update_learning with topic_version and evidence."""
    raise KBError('LEGACY_WRITE_DISABLED','旧写入接口已停用；请使用 update_learning 并提供 topic_version 和证据来源')

@tool

def record_conversation_update(conversation_id: str, messages: NormalizedMessages, request_id: str, actor: str='course-agent') -> dict:

    """导入规范化消息作为补充归档，不冒充本机原始日志。各消息需 role/content/timestamp。"""

    raw=normalized_raw(conversation_id,messages,request_id,actor); sha=digest(raw)
    path=archive_path(kb,conversation_id,sha,'.normalized.json')
    conv=kb.rows('SELECT id FROM conversations WHERE id=?',(conversation_id,))
    if not conv: raise KBError('NOT_FOUND','聊天未注册')

    def fn(c,u):

        c.execute('INSERT OR IGNORE INTO archives VALUES(?,?,?,?,?,?)',(sha,conversation_id,str(path),'normalized-import',len(raw),now()))

        # 补充消息使用负序号，与原始日志行号空间分离。

        seq=c.execute('SELECT COALESCE(MAX(seq),-1000000000000) FROM messages WHERE conversation_id=? AND seq<0',(conversation_id,)).fetchone()[0]; ids=[]

        for i,m in enumerate(messages):

            seq+=1; ident=digest([request_id,i]); ids.append(ident)

            c.execute('INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)',(ident,conversation_id,seq,m['role'],m['timestamp'],m['content'],sha,i+1))

        publish(path,raw)
        return {'message_ids':ids,'archive_sha256':sha}

    return kb.mutate('record_conversation_update',request_id,actor,conversation_id,messages,fn)

@tool

def rollback_update(update_id: str, request_id: str, actor: str='course-agent') -> dict:

    """回滚结构化变更并新增审计；后续更新存在时拒绝覆盖。"""

    return kb.rollback(update_id,request_id,actor)

@tool

def get_learning_overview() -> dict:

    """全部专题进度概览。"""

    return kb.overview()

@tool

def get_conversation_tree() -> list:

    """逻辑根、专题和原聊天关联，不代表原生聊天合并。"""

    return kb.rows('SELECT * FROM conversation_tree')

@tool

def get_update_history(entity_id: str|None=None, after_id: int=0, limit: int=5, full: bool=False) -> list:

    """分页审计；full=true 才返回完整 before/after。"""

    cols='*' if full else 'id,update_id,entity,entity_id'

    return kb.rows(f'SELECT {cols} FROM change_history WHERE id>? AND (? IS NULL OR entity_id=?) ORDER BY id LIMIT ?',(after_id,entity_id,entity_id,max(1,min(limit,100))))

@tool

def detect_knowledge_conflicts() -> dict:

    """检测明确标记的命题值冲突；返回所有版本，不自动裁决自然语言。"""

    return kb.conflicts()

@tool

def sync_conversation(conversation_id: str) -> dict:

    """主动只读同步已登记的本地会话日志；未登记来源返回错误。"""

    rows=kb.rows('SELECT source_path FROM conversations WHERE id=?',(conversation_id,))

    if not rows or not rows[0]['source_path']: raise KBError('SOURCE_UNAVAILABLE','先注册或使用规范化导入')

    return sync_file(kb,Path(rows[0]['source_path']))

@tool

def register_topic_conversation(name: str, canonical: str, conversation_id: str, title: str, cwd: str='', parent_topic_id: str|None=None) -> dict:

    """根据明确课程意图注册新聊天；相同 canonical 关联原专题，进阶分支可指定父专题。"""

    return kb.register(name,canonical,conversation_id,title,cwd,parent_id=parent_topic_id)

@tool

def identify_learning_intent(text: str) -> dict:

    """保守规则识别长期算法课程；未知领域由当前代理判断后注册。"""

    result=intent([{'role':'user','content':text}])

    return {'match':bool(result),'name':result[0] if result else None,'canonical':result[1] if result else None,'needs_review':bool(result and result[1]=='ambiguous')}

@tool

def get_sync_health() -> dict:

    """同步游标、待人工判定新课程和数据库一致性。"""

    return {'sync':kb.rows('SELECT * FROM sync_state'),'discovery':kb.rows('SELECT * FROM discovery_candidates'),'integrity':kb.rows('PRAGMA integrity_check'),'foreign_keys':kb.rows('PRAGMA foreign_key_check')}

@tool

def register_conversation(conversation_id: str, name: str='', canonical: str='', title: str='', cwd: str='', parent_topic_id: str|None=None, topic_id: str|None=None) -> dict:

    """仅未关联课程需注册：已有专题用 topic_id，新领域用 name；服务端解析别名/生成规范标识，不猜 canonical。已有聊天复用，矛盾参数报冲突。"""

    return context.register(name,canonical,conversation_id,title,cwd,parent_topic_id,topic_id)

@tool

def get_context_manifest(conversation_id: str|None=None, known_version: int|None=None, offset: int=0, limit: int=30, current_only: bool=False) -> dict:

    """L0 索引；恢复关联用 conversation_id + current_only=true，仅返回当前映射。registered=false 才需注册。"""

    return context.manifest(conversation_id,known_version,offset,limit,current_only)

@tool

def get_topic_context(topic_id: str, known_version: int|None=None, full: bool=False) -> dict:

    """L1 当前专题摘要；仅确实持有旧摘要时传 known_version。"""

    return context.topic(topic_id,known_version,full)

@tool

def get_topic_version(topic_id: str) -> dict:

    """只读取专题、摘要与归档版本。"""

    return context.version(topic_id)

@tool

def get_context_delta(topic_id: str, after_version: int, limit: int=5, full: bool=False) -> dict:

    """版本之后的变更；按 next_version 翻页，截短字段按需完整读取。"""

    return context.delta(topic_id,after_version,limit,full)

@tool

def search_knowledge(query: str='', topic_id: str|None=None, limit: int|None=None, related_to: str|None=None, since_version: int|None=None,

                     concepts: list[str]|None=None, topic_ids: list[str]|None=None, include_progress: bool=True, detail: Literal['compact','standard','detailed']='compact', cursor: str|None=None) -> dict:

    """L2：query旧式查询或concepts批量1..10个短语，每项独立limit。detail=compact/standard/detailed；批量进度为待核实投影。next_cursor续页，数据变化须重查。"""

    return context.search(query,topic_id,limit,related_to,since_version,concepts,topic_ids,include_progress,detail,cursor)



@tool

def read_knowledge(knowledge_id: str, known_version: int|None=None, field: str='content', offset: int=0, chars: int=3000) -> dict:

    """按字段分页读取知识原文；可传已持有的实体版本。"""

    return context.read(knowledge_id,known_version,field,offset,chars)

@tool

def get_global_overview(full: bool=False, offset: int=0, limit: int=30) -> dict:

    """全局索引；用户要求全部详细进度时才用 full=true。"""

    return context.overview(full,offset,limit)

@tool

def update_learning(topic_id: str, conversation_id: str, expected_version: int, request_id: str, changes: LearningChanges) -> dict:

    """原子增量更新；进度改变需 progress.set/append.evidence:string[]；新知识需 data.title/content/evidence，非 summary。期望版本为 topic_version；参数错误一次返回全部字段路径。"""

    return context.update(topic_id,conversation_id,expected_version,request_id,changes)

@tool

def get_conversation_history(conversation_id: str, after_seq: int|None=None, message_id: str|None=None, offset: int=0, chars: int=3000, latest: bool=False) -> dict:

    """L3 单条原文；latest 取最近消息；长消息用 message_id+next_offset 续读。"""

    return context.history(conversation_id,after_seq,message_id,offset,chars,latest)



if __name__=='__main__':
    transport=os.environ.get('ALGORITHM_MCP_TRANSPORT','stdio').strip().lower()
    if transport not in {'stdio','streamable-http'}:
        raise SystemExit('ALGORITHM_MCP_TRANSPORT must be stdio or streamable-http')
    if transport=='streamable-http':
        mcp.settings.host=os.environ.get('ALGORITHM_MCP_HOST','127.0.0.1')
        import ipaddress
        host=mcp.settings.host
        try:
            local=ipaddress.ip_address(host).is_loopback
        except ValueError:
            local=host.lower()=='localhost'
        if not local:
            raise SystemExit('UNSAFE_HTTP_BIND: HTTP requires a loopback host; use an authenticated SSH tunnel for remote access. Direct remote and multi-tenant deployment are unsupported.')
        mcp.settings.port=int(os.environ.get('ALGORITHM_MCP_PORT','8000'))
    mcp.run(transport=transport)
