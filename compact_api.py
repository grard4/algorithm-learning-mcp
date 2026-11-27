"""Compact read-only C2.3 API, using the reviewed R1 projection rules.

No legacy search, registration or write is performed by these two functions.
Pagination remembers explicit caller versions; it does not guess model memory.
"""
import base64
import json
import pathlib
import sys

import concept_reader as core

RULE = 'c23-compact-r2'


def versions_valid(versions):
    core.need(isinstance(versions,dict) and len(versions)<=10 and
              all(isinstance(k,str) and 0<len(k)<=128 and isinstance(v,str) and len(v)==64 and
                  all(ch in '0123456789abcdef' for ch in v) for k,v in versions.items()),
              'INVALID_KNOWN_VERSIONS')


def search(c, concepts, limit=2, topic_ids=None, cursor=None, known_versions=None):
    versions={} if known_versions is None else known_versions
    versions_valid(versions)
    core.need(not(cursor is not None and known_versions is not None),'CURSOR_WITH_KNOWN_VERSIONS')
    # Preserve input validation before hashing/sorting caller data.
    core.need(isinstance(concepts,list) and 1<=len(concepts)<=10 and
              all(isinstance(q,str) and q.strip() and len(q)<=120 for q in concepts),'INVALID_CONCEPTS')
    core.need(topic_ids is None or isinstance(topic_ids,list) and 1<=len(topic_ids)<=30 and
              all(isinstance(x,str) and x for x in topic_ids),'INVALID_TOPICS')
    signature=core.digest([RULE,concepts,limit,sorted(set(topic_ids or []))])
    raw_cursor=None
    if cursor is not None:
        core.need(isinstance(cursor,str) and 0<len(cursor)<=8192,'INVALID_CURSOR')
        try:envelope=json.loads(base64.urlsafe_b64decode(cursor))
        except Exception as ex:raise core.ReadError('INVALID_CURSOR') from ex
        core.need(isinstance(envelope,dict) and envelope.get('kind')==RULE,'CURSOR_NAMESPACE')
        core.need(envelope.get('signature')==signature,'CURSOR_QUERY_MISMATCH')
        raw_cursor=envelope.get('page')
        core.need(isinstance(raw_cursor,str) and bool(raw_cursor),'INVALID_CURSOR')
        versions=envelope.get('held');versions_valid(versions)
    raw=core.query(c,concepts,limit=limit,topic_ids=topic_ids,cursor=raw_cursor,detail='compact')
    groups=[];sources=[];source_lookup={};has_more=False
    for g in raw['groups']:
        if g['status']!='indexed':
            out={k:g[k] for k in ('query','status','concept_ids')}
            out.update(items=[],fallback='search_knowledge',has_more=False)
            groups.append(out);continue
        version=core.digest([RULE,g['projection_version']])
        unchanged=versions.get(g['concept_id'])==version
        items=[]
        if not unchanged:
            for item in g['items']:
                source=(item.get('topic_id'),item.get('conversation_id'))
                if source not in source_lookup:
                    source_lookup[source]=len(sources)
                    sources.append({'topic_id':source[0],'conversation_id':source[1]})
                compact={'event_seq':item['event_seq'],'knowledge_id':item['knowledge_id'],
                         'source_ref':source_lookup[source], 'source_version':item.get('source_version'),
                         'title':item.get('title',''), 'reusable':item['reusable']}
                if item['issues']:compact['issues']=item['issues']
                items.append(compact)
        more=g['has_more'] and not unchanged
        has_more |= more
        groups.append({'query':g['query'],'status':'unchanged' if unchanged else 'indexed',
                       'concept_id':g['concept_id'],'projection_version':version,
                       'items':items,'has_more':more})
    token=None
    if has_more:
        core.need(raw['next_cursor'] is not None,'INTERNAL_CURSOR_MISSING')
        token=base64.urlsafe_b64encode(json.dumps({'kind':RULE,'signature':signature,
                  'held':versions,'page':raw['next_cursor']},separators=(',',':')).encode()).decode()
    return {'rule':RULE,'state':'unknown','coverage':'approved_links_only',
            'groups':groups,'sources':sources,'next_cursor':token}


def read_link(c,event_seq):
    core.need(c.in_transaction and c.execute('PRAGMA query_only').fetchone()[0]==1,'READ_TRANSACTION_REQUIRED')
    core.need(type(event_seq) is int and event_seq>0,'INVALID_EVENT_SEQ')
    ev=c.execute("SELECT * FROM c_events WHERE seq=? AND kind='link'",(event_seq,)).fetchone()
    core.need(ev is not None,'LINK_NOT_FOUND')
    concept=c.execute('SELECT * FROM c_concepts WHERE id=?',(ev['concept_id'],)).fetchone()
    core.need(concept is not None,'CONCEPT_NOT_FOUND')
    projected=core.project(c,concept)
    item=next((x for x in projected['items'] if x['event_seq']==event_seq),None)
    retracted=item is None
    if retracted:
        item=core.inspect_link(c,ev);item['reusable']=False
        item['issues']=sorted(set(item['issues']+['LINK_RETRACTED']))
    # Detail is independently revalidated, never a cached copy of the search.
    proof=json.loads(ev['data'])
    return {'concept_id':ev['concept_id'],'canonical':concept['canonical'],'state':'unknown',
            'status':'retracted' if retracted else 'active',
            'concept_version':projected['concept_version'], 'link':item,
            'audit':{k:proof.get(k) for k in ['candidate_id','revision_hash','review_workpaper_hash',
                     'object_hash','package_hash','plan_hash','grant_hash']},
            'source_proof':proof.get('source'),
            'archive_file_validation':'not_rechecked_in_query'}
