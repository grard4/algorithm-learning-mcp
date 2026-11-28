"""Bounded context views and atomic learning patches. No implicit model-side cache."""

import json

import os

import re

from kb import KBError, digest, dump, now





def setting(name, default, ceiling):

    return max(1, min(int(os.environ.get('ALGORITHM_' + name, default)), ceiling))





def short(value, chars=180):

    text = value if isinstance(value, str) else dump(value)

    return text if len(text) <= chars else text[:chars] + '…'





def compact_value(value, count=5, chars=180):

    if isinstance(value, list):

        return [short(x, chars) for x in value[-count:]]

    if isinstance(value, dict):

        return {k: short(v, chars) for k, v in list(value.items())[-count:]}

    return short(value, chars) if isinstance(value, str) else value





class Context:

    def __init__(self, kb):

        self.kb = kb

        self.search_limit = setting('SEARCH_LIMIT', 5, 20)

        self.snippet_chars = setting('SNIPPET_CHARS', 220, 1000)

        self.context_items = setting('CONTEXT_ITEMS', 5, 20)



    def version_in(self, c, topic_id):

        if not c.execute('SELECT id FROM topics WHERE id=?', (topic_id,)).fetchone():

            raise KBError('NOT_FOUND', topic_id)

        row = c.execute('''SELECT COALESCE(MAX(e.change_id),0) topic_version,

            COALESCE(MAX(CASE WHEN e.entity='topic_progress' THEN e.change_id END),0) summary_version,

            MAX(u.timestamp) last_updated FROM context_events e

            JOIN change_history h ON h.id=e.change_id JOIN updates u ON u.id=h.update_id

            WHERE e.topic_id=?''', (topic_id,)).fetchone()

        sync = c.execute('''SELECT COALESCE(MAX(a.rowid),0) FROM archives a

            JOIN conversations v ON v.id=a.conversation_id WHERE v.topic_id=?''', (topic_id,)).fetchone()[0]

        return dict(topic_id=topic_id, **dict(row), last_sync_version=sync)



    def version(self, topic_id):

        with self.kb.connect() as c:

            c.execute('BEGIN')

            return self.version_in(c, topic_id)



    def manifest(self, conversation_id=None, known_version=None, offset=0, limit=30, current_only=False):

        if current_only and not conversation_id:

            raise KBError('INVALID', 'current_only 需要 conversation_id')

        if offset < 0:

            raise KBError('INVALID', 'offset 必须非负')

        limit = max(1, min(limit, 100))

        with self.kb.connect() as c:

            c.execute('BEGIN')

            version = c.execute('SELECT COALESCE(MAX(change_id),0) FROM context_events').fetchone()[0]

            current = None

            if conversation_id:

                row = c.execute('SELECT v.id conversation_id,v.topic_id,t.canonical FROM conversations v JOIN topics t ON t.id=v.topic_id WHERE v.id=?', (conversation_id,)).fetchone()

                current = dict(row) if row else {'conversation_id': conversation_id, 'registered': False}

            result = {'root': '算法竞赛学习', 'kb_version': version, 'current': current}

            if current_only:

                return result

            if known_version == version:

                return dict(result, unchanged=True)

            rows = c.execute('''SELECT t.id topic_id,t.name,t.parent_id,

                substr(COALESCE(json_extract(p.data,'$.stage'),'未知'),1,48) status

                FROM topics t JOIN topic_progress p ON p.id=t.id

                ORDER BY t.created_at,t.id LIMIT ? OFFSET ?''', (limit + 1, offset)).fetchall()

            result.update(topics=[dict(x) for x in rows[:limit]], next_offset=offset + limit if len(rows) > limit else None)

            return result



    def topic(self, topic_id, known_version=None, full=False):

        with self.kb.connect() as c:

            c.execute('BEGIN')

            version = self.version_in(c, topic_id)

            if known_version == version['topic_version']:

                return dict(version, unchanged=True)

            row = c.execute('SELECT * FROM topic_progress WHERE id=?', (topic_id,)).fetchone()

            data = json.loads(row['data'])

            if full:

                return dict(version, progress_version=row['version'], progress=data)

            keys = ('stage', 'mastery', 'taught', 'practiced', 'understood', 'mastered', 'pending',

                    'pending_exercises', 'next_step', 'decisions', 'teaching_policy')

            summary = {k: compact_value(data[k], self.context_items) for k in keys if k in data}

            for k in ('pending', 'pending_exercises'):

                if isinstance(data.get(k), list):

                    summary[k] = [short(x, 180) for x in data[k][:self.context_items]]

            clipped = [k for k in summary if summary[k] != data[k]]

            activity = c.execute('''SELECT m.id,m.conversation_id,m.seq,m.role,m.timestamp FROM messages m

                JOIN conversations v ON v.id=m.conversation_id WHERE v.topic_id=?

                ORDER BY m.timestamp DESC,m.seq DESC LIMIT 1''', (topic_id,)).fetchone()

            return dict(version, progress_version=row['version'], summary=summary,

                        clipped_fields=clipped, omitted_fields=[k for k in data if k not in summary],

                        recent_activity=dict(activity) if activity else None)



    def overview(self, full=False, offset=0, limit=30):

        manifest = self.manifest(offset=offset, limit=limit)

        if full:

            manifest['topics'] = [dict(t, context=self.topic(t['topic_id'], full=True)) for t in manifest['topics']]

        return manifest



    def delta(self, topic_id, after_version, limit=5, full=False):

        if after_version < 0:

            raise KBError('INVALID', '版本游标必须非负')

        limit = max(1, min(limit, 20))

        with self.kb.connect() as c:

            c.execute('BEGIN')

            version = self.version_in(c, topic_id)

            if after_version > version['topic_version']:

                raise KBError('CURSOR_AHEAD', '游标超出数据库版本；恢复备份后请完整重读专题')

            rows = c.execute('''SELECT h.* FROM context_events e JOIN change_history h ON h.id=e.change_id

                WHERE e.topic_id=? AND e.change_id>? ORDER BY e.change_id LIMIT ?''',

                             (topic_id, after_version, limit + 1)).fetchall()

            changes = []

            for row in rows[:limit]:

                before = json.loads(row['before_json']) if row['before_json'] else {}

                after = json.loads(row['after_json']) if row['after_json'] else {}

                item = {'cursor': row['id'], 'entity': row['entity'], 'id': row['entity_id'], 'deleted': not bool(after)}

                if after:

                    b = json.loads(before.get('data', '{}')); a = json.loads(after.get('data', '{}'))

                    patch = {k: v for k, v in a.items() if b.get(k) != v or k not in b}

                    patch.pop('recent_activity', None)

                    item['set'] = patch if full else {k: compact_value(v, 3, self.snippet_chars) for k, v in patch.items()}

                    item['removed'] = [k for k in b if k not in a]

                    item['clipped_fields'] = [k for k in patch if item['set'][k] != patch[k]]

                    item['version'] = after.get('version')

                    if row['entity'] in ('topics', 'conversations', 'conversation_tree'):

                        item['metadata'] = {k: after[k] for k in ('name', 'title', 'topic_id', 'parent_id', 'label') if k in after}

                changes.append(item)

            return dict(version, changes=changes, unchanged=not changes,

                        next_version=changes[-1]['cursor'] if changes else after_version, has_more=len(rows) > limit)



    def search(self, query='', topic_id=None, limit=None, related_to=None, since_version=None,

               concepts=None, topic_ids=None, include_progress=True, detail='compact', cursor=None):

        from search_engine import search

        return search(self,query,topic_id,limit,related_to,since_version,

                      concepts,topic_ids,include_progress,detail,cursor)



    def read(self, knowledge_id, known_version=None, field='content', offset=0, chars=3000):

        row = self.kb.get('knowledge_items', knowledge_id)

        result = {k: row[k] for k in ('id', 'topic_id', 'version', 'updated_at')}

        if known_version == row['version']:

            return dict(result, unchanged=True)

        if offset < 0 or field not in row['data']:

            raise KBError('INVALID', '未知字段或负 offset')

        text = row['data'][field]

        if not isinstance(text, str): text = dump(text)

        from public_response import public_text
        text = public_text(text)
        chars = max(1, min(chars, 12000)); end = offset + chars

        return dict(result, field=field, text=text[offset:end], offset=offset, total_chars=len(text),

                    next_offset=end if end < len(text) else None, fields=list(row['data']),

                    title=short(row['data'].get('title', ''), 100), status=row['data'].get('status', 'unknown'))



    def history(self, conversation_id, after_seq=None, message_id=None, offset=0, chars=3000, latest=False):

        if offset < 0: raise KBError('INVALID', 'offset 必须非负')

        if message_id:

            rows = self.kb.rows('SELECT * FROM messages WHERE id=? AND conversation_id=?', (message_id, conversation_id))

        else:

            ordering = 'timestamp DESC,seq DESC' if latest else 'seq'

            rows = self.kb.rows(f'''SELECT * FROM messages WHERE conversation_id=? AND (? IS NULL OR seq>?)

                ORDER BY {ordering} LIMIT 1''', (conversation_id, after_seq, after_seq))

        if not rows: return {'message': None, 'next_after_seq': after_seq}

        from public_response import public_text
        row = rows[0]; text = public_text(row.pop('content')); chars = max(1, min(chars, 12000)); end = offset + chars

        row.update(content=text[offset:end], offset=offset, total_chars=len(text), next_offset=end if end < len(text) else None)

        return {'message': row, 'next_after_seq': row['seq'] if end >= len(text) else after_seq}



    def register(self, name, canonical, conversation_id, title='', cwd='', parent_topic_id=None, topic_id=None):

        from topic_identity import resolve

        if not isinstance(conversation_id, str) or not conversation_id.strip():

            raise KBError('INVALID', '需要真实 conversation_id')

        with self.kb.connect() as c:

            c.execute('BEGIN')

            existing = c.execute('SELECT topic_id FROM conversations WHERE id=?', (conversation_id,)).fetchone()

            if existing and not any((name, canonical, topic_id, parent_topic_id)):

                return dict(conversation_id=conversation_id, **self.version_in(c, existing['topic_id']), already_registered=True)

            row, resolved = resolve(c, name, canonical, topic_id)

            if existing:

                if not row or row['id'] != existing['topic_id'] or (parent_topic_id is not None and row['parent_id'] != parent_topic_id):

                    raise KBError('TOPIC_CONFLICT', '当前聊天已关联其他专题，请核实范围')

                return dict(conversation_id=conversation_id, **self.version_in(c, row['id']), already_registered=True)

            if row:

                name, canonical = row['name'], row['canonical']

            else:

                canonical = resolved

        result = self.kb.register(name, canonical, conversation_id, title or name, cwd, parent_id=parent_topic_id)

        return dict(result, **{k: v for k, v in self.version(result['topic_id']).items() if k != 'topic_id'})



    def update(self, topic_id, conversation_id, expected_version, request_id, changes):

        from contracts import validate_changes

        if len(dump(changes)) > 100000:

            raise KBError('TOO_LARGE', '请拆分学习成果；单次最多 100000 字符')

        def fn(c, u):

            conv = c.execute('SELECT topic_id FROM conversations WHERE id=?', (conversation_id,)).fetchone()

            if not conv: raise KBError('NOT_FOUND', conversation_id)

            if conv['topic_id'] != topic_id:
                raise KBError('TOPIC_MISMATCH', '来源聊天与更新目标专题不一致；跨专题引用请使用 evidence_sources 或 relations')

            ver = self.version_in(c, topic_id)

            if ver['topic_version'] != expected_version:

                raise KBError('VERSION_CONFLICT', f"当前 topic_version={ver['topic_version']}；读取 delta 后合并重试")

            validate_changes(c, topic_id, request_id, changes)

            receipts = []

            touched = set()

            def evidence(data):

                refs = data.get('evidence', [])

                if not refs: raise KBError('EVIDENCE_REQUIRED', '请引用归档消息 ID')

                for ref in refs:

                    if not isinstance(ref, str) or not c.execute('SELECT id FROM messages WHERE id=?', (ref,)).fetchone():

                        raise KBError('EVIDENCE_NOT_FOUND', str(ref))

            def save(table, ident, data, old=None, extra=None):

                if old and json.loads(old['data']) == data:

                    receipts.append({'id': ident, 'unchanged': True}); return

                if (table, ident) in touched:

                    raise KBError('DUPLICATE_ENTITY', '同一批次内同一实体有不同修改，请先合并')

                touched.add((table, ident))

                row = dict(old) if old else dict(id=ident, **(extra or {}))

                row.update(data=dump(data), version=old['version'] + 1 if old else 1, updated_at=now())

                self.kb.change(c, u, table, ident, row)

                receipts.append({'id': ident, 'version': row['version']})

            patch = changes.get('progress')

            if patch is not None:

                if not isinstance(patch, dict) or set(patch) - {'set', 'append', 'remove'}:

                    raise KBError('INVALID', 'progress 使用 set/append/remove')

                old = c.execute('SELECT * FROM topic_progress WHERE id=?', (topic_id,)).fetchone()

                data = json.loads(old['data'])

                if not isinstance(patch.get('set', {}), dict): raise KBError('INVALID', 'set 必须是对象')

                data.update(patch.get('set', {}))

                for op in ('append', 'remove'):

                    if not isinstance(patch.get(op, {}), dict): raise KBError('INVALID', op + ' 必须是对象')

                    for key, values in patch.get(op, {}).items():

                        if not isinstance(values, list) or not isinstance(data.get(key, []), list):

                            raise KBError('INVALID', 'append/remove 只支持列表字段')

                        target = data.setdefault(key, [])

                        for value in values:

                            if op == 'append' and value not in target: target.append(value)

                            if op == 'remove' and value in target: target.remove(value)

                if data != json.loads(old['data']):

                    refs = patch.get('set', {}).get('evidence', []) + patch.get('append', {}).get('evidence', [])

                    evidence({'evidence': refs})

                for key in ('stage', 'mastery'):

                    if not isinstance(data.get(key), str): raise KBError('INVALID', key + ' 必须是字符串')

                for key in ('taught','practiced','understood','mastered','pending','completed_exercises','pending_exercises','conclusions','common_errors','evidence'):

                    if not isinstance(data.get(key), list): raise KBError('INVALID', key + ' 必须是数组')

                evidence(data); save('topic_progress', topic_id, data, old)

            for group, table in (('knowledge', 'knowledge_items'), ('tasks', 'learning_tasks')):

                entries = changes.get(group, [])

                if not isinstance(entries, list) or len(entries) > 20: raise KBError('INVALID', group + ' 最多 20 项')

                for index, entry in enumerate(entries):

                    if not isinstance(entry, dict) or not isinstance(entry.get('data'), dict): raise KBError('INVALID', '条目需要 data 对象')

                    ident = entry.get('id') or digest([group, request_id, index])

                    old = c.execute(f'SELECT * FROM {table} WHERE id=?', (ident,)).fetchone()

                    if old and (old['topic_id'] != topic_id or old['version'] != entry.get('expected_version')):

                        raise KBError('VERSION_CONFLICT', '实体版本或专题不匹配')

                    before = json.loads(old['data']) if old else {}

                    data = dict(before, **entry['data']); evidence(data)

                    if not isinstance(data.get('title'), str) or not data['title']: raise KBError('INVALID', '需要字符串 title')

                    data.setdefault('source_conversation', conversation_id)

                    if group == 'knowledge':

                        if not isinstance(data.get('content'), str) or not data['content']: raise KBError('INVALID', '需要字符串 content')

                        if before.get('claim_key') and (before.get('claim_key'), before.get('claim_value')) != (data.get('claim_key'), data.get('claim_value')):

                            raise KBError('CLAIM_CONFLICT', '命题改变须另建条目并关联 conflicts')

                        if before.get('status') in ('verified', 'reviewed_summary') and before.get('content') != data.get('content') and not entry['data'].get('verification'):

                            raise KBError('REVIEW_REQUIRED', '修改已审核结论需要本次 verification 或另建候选')

                        data['content_hash'] = digest(data['content'].strip())

                        if not old:

                            duplicate = c.execute("SELECT * FROM knowledge_items WHERE topic_id=? AND (json_extract(data,'$.content_hash')=? OR trim(json_extract(data,'$.content'))=?)", (topic_id, data['content_hash'], data['content'].strip())).fetchone()

                            if duplicate:

                                existing = json.loads(duplicate['data'])

                                if (existing.get('claim_key'), existing.get('claim_value')) == (data.get('claim_key'), data.get('claim_value')):

                                    merged = dict(existing)

                                    merged['evidence'] = list(dict.fromkeys(existing.get('evidence', []) + data['evidence']))

                                    if existing.get('evidence_sources') or data.get('evidence_sources'):
                                        merged['evidence_sources'] = {**existing.get('evidence_sources', {}), **data.get('evidence_sources', {})}

                                    validate_changes(c, topic_id, request_id, {'knowledge': [{
                                        'id': duplicate['id'], 'expected_version': duplicate['version'], 'data': merged}]})

                                    save(table, duplicate['id'], merged, duplicate)

                                    continue

                        data.setdefault('status', 'candidate')

                    elif data.get('status') not in ('pending', 'attempted', 'completed', 'unknown'):

                        raise KBError('INVALID', '练习 status 无效')

                    save(table, ident, data, old, {'topic_id': topic_id})

            relations = changes.get('relations', [])

            if not isinstance(relations, list) or len(relations)>20: raise KBError('INVALID', 'relations 最多 20 项')

            for rel in relations:

                if rel['source_id'] == rel['target_id']: raise KBError('INVALID', '不能自关联')

                if not c.execute('SELECT id FROM knowledge_items WHERE id IN (?,?) AND topic_id=?', (rel['source_id'], rel['target_id'], topic_id)).fetchone():

                    raise KBError('INVALID', '关联至少一端属于当前专题')

                ident = digest([rel['source_id'], rel['target_id'], rel['kind']])

                old = c.execute('SELECT * FROM knowledge_relations WHERE id=?', (ident,)).fetchone()

                save('knowledge_relations', ident, {'reason': rel['reason']}, old,

                     {k: rel[k] for k in ('source_id', 'target_id', 'kind')})

            return dict(self.version_in(c, topic_id), changes=receipts)

        return self.kb.mutate('update_learning', request_id, 'course-agent', conversation_id,

                              [topic_id, expected_version, changes], fn)
