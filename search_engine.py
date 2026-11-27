"""Deterministic read-only retrieval. Query aliases are not a persisted concept index."""

import base64,hashlib,json,re,unicodedata

from kb import KBError

RULE='search-b1'

ALIASES={

 'splay':('Splay',('Splay','Splay Tree','伸展树')),

 'lct':('Link-Cut Tree',('LCT','Link-Cut Tree')),

 'tree_dp':('树形 DP',('树形 DP','树上动态规划','Tree DP')),

 'rerooting_dp':('换根 DP',('换根 DP','Rerooting DP')),

 'dp':('动态规划',('DP','动态规划')),

 'network_flow':('网络流',('网络流','Network Flow')),

 'dinic':('Dinic',('Dinic',)),

 'bipartite_matching':('二分图匹配',('二分图匹配','Bipartite Matching')),

 'kuhn':('Kuhn',('Kuhn','Kuhn Algorithm')),

 'hopcroft_karp':('Hopcroft-Karp',('Hopcroft-Karp',)),

 'km':('KM',('KM','Kuhn-Munkres')),

 'scanline':('扫描线',('扫描线','Scanline')),

 'cdq':('CDQ',('CDQ',)),

 'segment_tree':('线段树',('线段树','Segment Tree')),

 'linear_basis':('线性基',('线性基','Linear Basis'))}

AMBIGUOUS={'动态树':('lct','other_dynamic_tree'),'匈牙利算法':('kuhn','km')}

def norm(s):

 s=unicodedata.normalize('NFKC',s).casefold()

 return re.sub(r'\s+','',s.replace('–','-').replace('—','-').replace('‑','-'))

def clean(s):

 s=re.sub(r'<oai-mem-citation>.*?</oai-mem-citation>',' ',str(s),flags=re.S)

 s=re.sub(r'```.*?```',' ',s,flags=re.S)

 s=re.sub(r'\[[^\]]*\]\([^)]*\)',lambda m: m[0].split('](')[0][1:],s)

 s=re.sub(r'(?:https?://|[A-Za-z]:[\\/]|(?:\.\.?/)?(?:[\w.-]+[\\/])+)[^\s<>"\u3002]*',' ',s)

 s=re.sub(r'\b[\w.-]+\.(?:md|py|cpp|jsonl?|txt|sqlite3)\b',' ',s,flags=re.I)

 s=re.sub(r'.*?',' ',s)

 return s

def snippet(text,aliases,chars):

 text=clean(text)

 for alias in aliases:

  pattern=r'\s*'.join(re.escape(x) for x in alias.split())

  hit=re.search(pattern,text,re.I)

  if hit:return text[max(0,hit.start()-40):max(0,hit.start()-40)+chars]

 return text[:chars]



def identity(q):

 if not q.strip():return None,q,(),[]

 n=norm(q)

 if n in AMBIGUOUS:return n,q,(),list(AMBIGUOUS[n])

 for key,(name,aliases) in ALIASES.items():

  if n in [norm(x) for x in aliases]:return key,name,aliases,[]

 return None,q,(q,),[]

def match(text,aliases,key=None):

 text=clean(text)

 if key=='dp':

  for x in ALIASES['tree_dp'][1]+ALIASES['rerooting_dp'][1]:

   text=re.sub(re.escape(x).replace(r'\ ',r'\s*'),' ',text,flags=re.I)

 text=unicodedata.normalize('NFKC',text).casefold().replace('–','-').replace('—','-').replace('‑','-')

 for a in aliases:

  a=unicodedata.normalize('NFKC',a).casefold()

  parts=re.split(r'\s+',a.strip());pattern=r'\s*'.join(re.escape(p) for p in parts)

  if a and a[0].isascii() and a[0].isalnum():pattern=r'(?<![a-z0-9_])'+pattern

  if a and a[-1].isascii() and a[-1].isalnum():pattern+=r'(?![a-z0-9_])'

  if re.search(pattern,text):return True

 return False



def search(cx,query='',topic_id=None,limit=None,related_to=None,since_version=None,

           concepts=None,topic_ids=None,include_progress=True,detail='compact',cursor=None):

 batch=concepts is not None

 def invalid(msg):raise KBError('INVALID',msg)

 if not isinstance(query,str) or len(query)>500:invalid('query: 需要最多500字符的string')

 if cursor is not None and (not isinstance(cursor,str) or len(cursor)>16384):invalid('cursor: 需要最多16384字符的string')

 if batch and (not isinstance(concepts,list) or not 1<=len(concepts)<=10 or any(not isinstance(q,str) or not q.strip() or len(q)>120 for q in concepts)):invalid('concepts: 需要1..10个非空string，每个最多120字符')

 if batch and (query.strip() or related_to or since_version is not None):invalid('concepts不能同时使用query/related_to/since_version')

 if not batch and not query.strip() and not related_to:invalid('需要query、concepts或related_to')

 if detail not in ('compact','standard','detailed'):invalid('detail: compact|standard|detailed')

 if type(include_progress) is not bool:invalid('include_progress: 需要bool')

 if limit is not None and (type(limit) is not int or limit<1):invalid('limit: 需要正整数')

 limit=min(limit or (2 if batch else cx.search_limit),20)

 if topic_ids is not None and (not isinstance(topic_ids,list) or not topic_ids or len(topic_ids)>30 or any(not isinstance(t,str) or not t for t in topic_ids)):invalid('topic_ids: 需要1..30个非空string')

 if topic_id is not None and not isinstance(topic_id,str):invalid('topic_id: 需要string')

 if topic_id and topic_ids and topic_id not in topic_ids:invalid('topic_id与topic_ids冲突')

 filters=[topic_id] if topic_id else sorted(set(topic_ids or []))

 queries=concepts if batch else [query.strip()]

 if len({norm(q) for q in queries})!=len(queries):invalid('concepts包含重复查询')

 if since_version is not None and (type(since_version) is not int or since_version<0):invalid('since_version: 需要非负整数')

 signature=hashlib.sha256(json.dumps([queries,filters,limit,related_to,since_version,include_progress,detail,RULE],ensure_ascii=False).encode()).hexdigest()

 with cx.kb.connect() as c:

  c.execute('BEGIN')

  topics={x['id']:dict(x) for x in c.execute('SELECT * FROM topics')}

  if any(t not in topics for t in filters):raise KBError('NOT_FOUND','topic filter不存在')

  # All reads in one SQLite snapshot; archives can change without context_events.

  version=[c.execute('SELECT COALESCE(MAX(id),0) FROM change_history').fetchone()[0],c.execute('SELECT COALESCE(MAX(rowid),0) FROM archives').fetchone()[0],c.execute('SELECT COUNT(*) FROM messages').fetchone()[0]]
  version.append(c.execute('SELECT epoch FROM r3_meta WHERE singleton=1').fetchone()[0])

  offsets=[0]*len(queries)

  if cursor:

   try:

    data=json.loads(base64.urlsafe_b64decode(cursor.encode()))

    if data['signature']!=signature:invalid('cursor不属于当前查询')

    if data['version']!=version:raise KBError('CURSOR_STALE','数据版本变化，请从第一页重查')

    offsets=data['offsets']

    if len(offsets)!=len(queries) or any(type(x) is not int or x<0 for x in offsets):invalid('cursor offsets无效')

   except KBError:raise

   except Exception:invalid('cursor格式无效')

  where=' WHERE topic_id IN ('+','.join('?' for _ in filters)+')' if filters else ''

  raw=[dict(x) for x in c.execute('SELECT * FROM knowledge_items'+where+' ORDER BY id LIMIT 5001',filters)]

  incomplete=len(raw)>5000;raw=raw[:5000]

  for x in raw:x['data']=json.loads(x['data'])

  changed=None

  if since_version is not None:changed={x[0] for x in c.execute("SELECT entity_id FROM context_events WHERE entity='knowledge_items' AND change_id>?",(since_version,))}

  related=set()

  if related_to:

   if not c.execute('SELECT id FROM knowledge_items WHERE id=?',(related_to,)).fetchone():raise KBError('NOT_FOUND',related_to)

   for x in c.execute('SELECT source_id,target_id FROM knowledge_relations WHERE source_id=? OR target_id=?',(related_to,related_to)):related.add(x[1] if x[0]==related_to else x[0])

  progress=[dict(x) for x in c.execute('SELECT * FROM topic_progress') if not filters or x['id'] in filters] if batch and include_progress else []

  messages=[];history_loaded=False;history_incomplete=False

  # Memoize only inside this read transaction; no cross-snapshot evidence cache.
  evidence_exists={}

  def refs(ids):
   found=[]
   for m in ids:
    if not isinstance(m,str):continue
    if m not in evidence_exists:
     evidence_exists[m]=bool(c.execute('SELECT 1 FROM messages WHERE id=?',(m,)).fetchone())
    if evidence_exists[m]:found.append(m)
   return found

  groups=[];next_offsets=[];more=False

  for qi,q in enumerate(queries):

   key,name,aliases,ambiguity=identity(q);found=[]

   for row in raw:

    d=row['data'];hit=(row['id'] in related) or (aliases and any(match(d.get(f,''),aliases,key) for f in ('title','content','summary'))) or any(norm(t) in {norm(a) for a in aliases} for t in d.get('tags',[]) if isinstance(t,str))

    if not hit or (changed is not None and row['id'] not in changed):continue

    title=clean(d.get('title',''))[:80];summary=snippet(d.get('summary') or d.get('content',''),aliases,cx.snippet_chars)

    item={'id':row['id'],'topic_id':row['topic_id'],'version':row['version'],'title':title,'summary':summary,'status':d.get('status','unknown'),'source_conversation':d.get('source_conversation'),'evidence':d.get('evidence',[])[:2]}

    score=(int(row['id'] in related),int(match(title,aliases,key)),row['updated_at'],row['id'])

    found.append((score,item))

   found.sort(key=lambda x:x[0],reverse=True)

   states=[]

   for row in progress:

    d=json.loads(row['data'])

    for field,state in [('pending','planned'),('taught','taught'),('practiced','practiced'),('understood','understood'),('mastered','mastered')]:

     for entry in d.get(field,[]):

      if not match(entry if isinstance(entry,str) else json.dumps(entry,ensure_ascii=False),aliases,key):continue

      evidence=refs(d.get('evidence',[]));scope='exact' if isinstance(entry,str) and norm(clean(entry)) in {norm(a) for a in aliases} else 'mention'

      effective=state if evidence and scope=='exact' and state in ('planned','taught','practiced') else 'unknown'

      # Progress evidence belongs to the whole topic record, not to this exact assertion.

      s={'topic_id':row['id'],'reported_state':state,'state':effective,'evidence_type':'planned_only' if state=='planned' else 'topic_record','needs_review':True,'match_scope':scope}

      if detail!='compact':s.update(version=row['version'],evidence=evidence[:2],evidence_count=len(evidence),evidence_scope='topic_not_concept')

      if detail=='detailed':s['summary']=clean(entry)[:180]

      states.append(s)

   # Bound progress output separately; disclosure rather than silent truncation.

   states.sort(key=lambda s:(s['topic_id'],s['reported_state']))

   unique={json.dumps(x,sort_keys=True):x for x in states};states=list(unique.values())

   state_conflict=len({x['reported_state'] for x in states})>1

   history=[]

   if batch and not found and not states and not ambiguity:

    if not history_loaded:

     args=filters

     w=' WHERE v.topic_id IN ('+','.join('?' for _ in filters)+')' if filters else ''

     messages=[dict(x) for x in c.execute('SELECT m.id,m.conversation_id,m.content,m.role,m.seq,v.topic_id FROM messages m JOIN conversations v ON v.id=m.conversation_id'+w+' ORDER BY m.seq DESC,m.id LIMIT 2001',args)]

     history_incomplete=len(messages)>2000;messages=messages[:2000];history_loaded=True

    for m in messages:

     if 'AGENTS.md instructions' in m['content'] or 'environment_context' in m['content']:continue

     if match(m['content'],aliases,key):

      h={'message_id':m['id'],'topic_id':m['topic_id'],'conversation_id':m['conversation_id'],'state':'unknown','evidence_type':'mention_only'}

      if detail=='detailed':h['summary']=snippet(m['content'],aliases,180)

      history.append(h)

   # Page combined knowledge and history per query; no one query steals another's limit.

   combined=[x[1] for x in found]+history

   start=offsets[qi];page=combined[start:start+limit];has_more=start+limit<len(combined)

   next_offsets.append(start+len(page));more|=has_more

   if batch:

    state_values={s['state'] for s in states}

    action='review_conflict' if state_conflict else 'verify_prerequisite' if 'planned' in state_values else 'review_evidence' if states or found or history else 'keep_unknown'

    items=[]

    for item in page:

     if 'message_id' in item:items.append(item);continue

     x={k:item[k] for k in ('id','topic_id','version','status')};x['state']='unknown'

     if detail!='compact':x.update(title=item['title'],source_conversation=item['source_conversation'],evidence=item['evidence'])

     if detail=='detailed':x['summary']=item['summary']

     items.append(x)

    groups.append({'query':q,'concept_key':key,'name':name,'ambiguous':ambiguity,'matched':bool(combined or states),'items':items,'progress':states[:20],'progress_truncated':len(states)>20,'needs_review':bool(states or combined or ambiguity),'conflict':state_conflict,'action':action,'has_more':has_more})

   else:groups=page

  result={'groups':groups} if batch else {'items':groups}

  token=None

  if more:token=base64.urlsafe_b64encode(json.dumps({'signature':signature,'version':version,'offsets':next_offsets},separators=(',',':')).encode()).decode()

  result.update(has_more=more,next_cursor=token,retrieval='normalized-phrase-aliases',coverage='incomplete' if incomplete or history_incomplete else 'bounded_sources',version=version,rule_version=RULE)

  if batch:result['limits']={'knowledge':5000,'history_messages':2000,'progress_per_concept':20}

  return result
