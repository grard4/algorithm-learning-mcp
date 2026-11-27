"""C2.3 read-adapter candidate. No schema, import, event or learning writes.

The caller provides an existing read transaction with query_only=ON. Matching
query aliases never creates concepts or infers mastery. C2.2 executor link-v1
events are supported; older prototype layouts fail closed, not silently read.
"""
import base64
import hashlib
import json
import re
import unicodedata

RULE = 'c23-read-v1'
MAX_EVENTS = 500
MAX_CONCEPTS = 1000
def concept_aliases(c, concept_id):
    aliases = []
    for row in c.execute("SELECT data FROM c_events WHERE concept_id=? AND kind='alias'", (concept_id,)):
        try:
            data = json.loads(row['data'])
        except (TypeError, ValueError):
            continue
        value = data.get('normalized')
        if isinstance(value, str) and value.strip():
            aliases.append(value)
    return aliases



class ReadError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def need(condition, code):
    if not condition:
        raise ReadError(code)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def text_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def norm(text):
    return re.sub(r'[\s_‐‑–—-]+', '', unicodedata.normalize('NFKC', text).casefold())


def row(c, table, ident):
    return c.execute('SELECT * FROM '+table+' WHERE id=?', (ident,)).fetchone()


def inspect_link(c, event):
    data = json.loads(event['data'])
    source = data.get('source')
    result = {'event_seq': event['seq'], 'knowledge_id': event['knowledge_id'],
              'topic_id': event['topic_id'], 'conversation_id': event['conversation_id'],
              'state': 'unknown', 'reusable': False, 'issues': [],
              'request_id': event['request_id'], 'package_hash': data.get('package_hash'),
              'candidate_id': data.get('candidate_id'), 'revision_hash': data.get('revision_hash'),
              'object_hash': data.get('object_hash'), 'plan_hash': data.get('plan_hash'),
              'archive_file_validation': 'not_rechecked_in_query'}
    if not isinstance(source, dict):
        result['issues'].append('UNSUPPORTED_LINK_LAYOUT')
        return result
    required = ['knowledge_id', 'knowledge_version', 'knowledge_data_sha256',
                'source_conversation', 'topic_id', 'evidence']
    if any(k not in source for k in required) or not isinstance(source['evidence'], list) or not source['evidence']:
        result['issues'].append('SOURCE_PROOF_MISSING')
        return result
    kid, cid, tid = source['knowledge_id'], source['source_conversation'], source['topic_id']
    result.update(knowledge_id=kid, conversation_id=cid, topic_id=tid,
                  source_version=source['knowledge_version'], evidence=[])
    k = row(c, 'knowledge_items', kid)
    cv = row(c, 'conversations', cid)
    topic = row(c, 'topics', tid)
    observed = [dict(k) if k else None, dict(cv) if cv else None, dict(topic) if topic else None]
    if event['knowledge_id'] != kid or event['conversation_id'] != cid or event['topic_id'] != tid:
        result['issues'].append('EVENT_SOURCE_ID_CHANGED')
    if not k or k['topic_id'] != tid or k['version'] != source['knowledge_version'] or text_hash(k['data']) != source['knowledge_data_sha256']:
        result['issues'].append('KNOWLEDGE_SOURCE_CHANGED')
    if not cv or cv['topic_id'] != tid or not topic:
        result['issues'].append('SOURCE_RELATION_CHANGED')
    if len(source['evidence']) > 20:
        result['issues'].append('EVIDENCE_LIMIT')
    for ev in source['evidence'][:20]:
        if not isinstance(ev, dict) or not all(x in ev for x in ['message_id','archive_sha256','content_sha256','locator','role','seq','conversation_id']):
            result['issues'].append('EVIDENCE_PROOF_MISSING')
            continue
        m = row(c, 'messages', ev['message_id'])
        a = c.execute('SELECT * FROM archives WHERE sha256=?', (ev['archive_sha256'],)).fetchone()
        observed.extend([dict(m) if m else None, dict(a) if a else None])
        if (not m or not a or m['conversation_id'] != cid or ev['conversation_id'] != cid or
            a['conversation_id'] != cid or m['source_hash'] != ev['archive_sha256'] or
            m['source_line'] != ev['locator'] or m['seq'] != ev['seq'] or
            m['role'] != ev['role'] or text_hash(m['content']) != ev['content_sha256']):
            result['issues'].append('MESSAGE_SOURCE_CHANGED')
        result['evidence'].append({'message_id': ev['message_id'], 'archive_sha256': ev['archive_sha256'],
                                   'role': ev['role'], 'form': ev.get('form', 'unknown')})
    result['source_observation'] = digest(observed)
    result['issues'] = sorted(set(result['issues']))
    result['reusable'] = not result['issues']
    if k:
        kd = json.loads(k['data'])
        result['title'] = str(kd.get('title', ''))[:80]
        result['summary'] = str(kd.get('summary') or kd.get('content') or '')[:180]
    return result


def project(c, concept):
    cid = concept['id']
    events = c.execute('SELECT * FROM c_events WHERE concept_id=? ORDER BY seq LIMIT ?',
                       (cid, MAX_EVENTS+1)).fetchall()
    need(len(events) <= MAX_EVENTS, 'CONCEPT_EVENT_LIMIT')
    removed = {x['target_seq'] for x in events if x['kind'] == 'retract'}
    links = [inspect_link(c, x) for x in events if x['kind'] == 'link' and x['seq'] not in removed]
    # Detect cross-concept/corrupt retractions without treating them as legitimate.
    invalid = c.execute('''SELECT 1 FROM c_events x JOIN c_events y ON x.target_seq=y.seq
                            WHERE (x.concept_id=? OR y.concept_id=?) AND
                            (x.concept_id<>y.concept_id OR x.kind<>'retract') LIMIT 1''', (cid,cid)).fetchone()
    need(not invalid, 'INVALID_RETRACTION')
    duplicates = {}
    for item in links:
        duplicates.setdefault(item['knowledge_id'], []).append(item)
    for group in duplicates.values():
        if len(group) > 1:
            for item in group:
                item['issues'].append('MULTIPLE_ACTIVE_LINKS_REVIEW');item['reusable'] = False
    # Assertions/scopes are intentionally NOT projected into learning state in
    # the link-only milestone, including user reports or teacher conclusions.
    unhandled = any(x['kind'] in ('assertion','scope') and x['seq'] not in removed for x in events)
    return {'concept_id':cid,'canonical':concept['canonical'], 'state':'unknown',
            'concept_version':max((x['version'] for x in events),default=0),
            'projection_version':digest([RULE,dict(concept),[dict(x) for x in events],links]),
            'items':links,'state_projection':'not_enabled', 'state_records_present':unhandled}


def query(c, concepts, *, limit=2, topic_ids=None, cursor=None, known_versions=None, detail='compact'):
    need(c.in_transaction and c.execute('PRAGMA query_only').fetchone()[0] == 1, 'READ_TRANSACTION_REQUIRED')
    need(isinstance(concepts,list) and 1<=len(concepts)<=10 and
         all(isinstance(q,str) and q.strip() and len(q)<=120 for q in concepts), 'INVALID_CONCEPTS')
    need(len({norm(q) for q in concepts})==len(concepts), 'DUPLICATE_QUERY')
    need(type(limit) is int and 1<=limit<=5, 'INVALID_LIMIT')
    need(detail in ('compact','standard'), 'INVALID_DETAIL')
    need(topic_ids is None or isinstance(topic_ids,list) and 1<=len(topic_ids)<=30 and
         all(isinstance(x,str) and x for x in topic_ids), 'INVALID_TOPICS')
    filters=sorted(set(topic_ids or []))
    need(all(row(c,'topics',t) for t in filters), 'TOPIC_NOT_FOUND')
    known_versions={} if known_versions is None else known_versions
    need(isinstance(known_versions,dict) and all(isinstance(k,str) and isinstance(v,str) and len(v)==64 for k,v in known_versions.items()), 'INVALID_KNOWN_VERSIONS')
    need(not(cursor and known_versions), 'CURSOR_WITH_KNOWN_VERSIONS')
    catalog=c.execute('SELECT * FROM c_concepts ORDER BY id LIMIT ?', (MAX_CONCEPTS+1,)).fetchall()
    need(len(catalog)<=MAX_CONCEPTS,'CONCEPT_CATALOG_LIMIT')
    signature=digest([RULE,concepts,filters,limit,detail])
    groups=[];versions=[]
    for term in concepts:
        matches=[]
        for co in catalog:
            names=[co['id'],co['canonical'],co['name'],*concept_aliases(c,co['id'])]
            if norm(term) in {norm(n) for n in names}:matches.append(co)
        if len(matches)!=1:
            groups.append({'query':term,'status':'ambiguous' if matches else 'not_indexed',
                           'concept_ids':[x['id'] for x in matches], 'state':'unknown','items':[],
                           'legacy_fallback_allowed':True})
            versions.append(digest([dict(x) for x in matches]));continue
        p=project(c,matches[0]);versions.append(p['projection_version'])
        p.update(query=term,status='indexed',legacy_fallback_allowed=False)
        if filters:p['items']=[x for x in p['items'] if x['topic_id'] in filters]
        p['projection_version']=digest([p['projection_version'],filters])
        if known_versions.get(p['concept_id'])==p['projection_version']:
            p['items']=[];p['unchanged']=True
        else:p['unchanged']=False
        groups.append(p)
    state=digest([versions,signature]);offsets=[0]*len(groups)
    if cursor is not None:
        need(isinstance(cursor,str) and len(cursor)<=4096,'INVALID_CURSOR')
        try:decoded=json.loads(base64.urlsafe_b64decode(cursor))
        except Exception as ex:raise ReadError('INVALID_CURSOR') from ex
        need(isinstance(decoded,dict) and decoded.get('signature')==signature,'CURSOR_QUERY_MISMATCH')
        need(decoded.get('state')==state,'CURSOR_STALE')
        offsets=decoded.get('offsets')
        need(isinstance(offsets,list) and len(offsets)==len(groups) and all(type(x) is int and x>=0 for x in offsets),'INVALID_CURSOR')
    more=False;next_offsets=[]
    for g,off in zip(groups,offsets):
        all_items=g['items'];need(off<=len(all_items),'INVALID_CURSOR')
        page=all_items[off:off+limit];g['has_more']=off+len(page)<len(all_items)
        next_offsets.append(off+len(page));more |= g['has_more']
        if detail=='compact':
            page=[{k:v for k,v in x.items() if k not in ('summary','source_observation')} for x in page]
            for item in page:
                ev=item.get('evidence',[]);item['evidence_count']=len(ev);item['evidence']=ev[:2]
        g['items']=page
    token=base64.urlsafe_b64encode(json.dumps({'signature':signature,'state':state,'offsets':next_offsets}).encode()).decode() if more else None
    return {'rule_version':RULE,'groups':groups,'has_more':more,'next_cursor':token,
            'incremental_mode':'caller_projection_versions','source_invalidation':'read_time',
            'automatic_event_writes':False,'coverage':'approved_links_only'}
