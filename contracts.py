"""One JSON Schema for MCP discovery and transactional, non-coercing validation."""
import copy
import json
from typing import Annotated, Any
from jsonschema import Draft202012Validator
from pydantic import WithJsonSchema
from kb import KBError, digest

TEXT = {'type': 'string', 'minLength': 1}
REFS = {'type': 'array', 'items': TEXT, 'minItems': 1,
        'description': '归档 messages.id 字符串数组；不是对象数组。'}
EVIDENCE_SOURCES = {'type': 'object', 'additionalProperties': {
    'type': 'object', 'additionalProperties': False,
    'required': ['conversation_id', 'topic_id', 'scope'],
    'properties': {'conversation_id': TEXT, 'topic_id': TEXT,
                   'scope': {'enum': ['same_topic', 'cross_topic']}}}}
LIST_FIELDS = ('taught', 'practiced', 'understood', 'mastered', 'pending',
               'completed_exercises', 'pending_exercises', 'conclusions', 'common_errors')
progress_fields = {key: {'type': 'array', 'items': {}} for key in LIST_FIELDS}
progress_fields.update(stage={'type': 'string'}, mastery={'type': 'string'}, evidence=REFS,
                       evidence_sources=EVIDENCE_SOURCES)
list_fields = {key: value for key, value in progress_fields.items() if value['type'] == 'array'}


def entry_schema(kind):
    fields = dict(title=TEXT, evidence=REFS, evidence_sources=EVIDENCE_SOURCES, source_conversation=TEXT)
    if kind == 'knowledge':
        fields.update(content=TEXT, status={'type': 'string'}, claim_key={'type': 'string'},
                      claim_value={}, verification={}, tags={'type': 'array', 'items': {'type': 'string'}})
        required = ['title', 'content', 'evidence']
    else:
        fields['status'] = {'enum': ['pending', 'attempted', 'completed', 'unknown']}
        required = ['title', 'status', 'evidence']
    return {
        'type': 'object', 'additionalProperties': False, 'required': ['data'],
        'properties': {'id': {**TEXT, 'description': '可选自定义新 ID；已存在时为修改。'},
                       'expected_version': {'type': 'integer', 'minimum': 0,
                                            'description': '修改已存在的 id 时必填当前实体版本；新建不需要。'},
                       'data': {'type': 'object', 'properties': fields, 'additionalProperties': True,
                                'description': '新建需必填字段；id 更新可省略未修改字段，继承旧值。扩展元数据保留。'}},
        'allOf': [
            {'if': {'not': {'required': ['id']}},
             'then': {'properties': {'data': {'required': required}}}}
        ]}


CHANGES_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'properties': {
        'progress': {'type': 'object', 'additionalProperties': False,
            'description': '实际改变进度时，set.evidence 或 append.evidence 必须提供本次归档 ID；合并后的 evidence 也须非空。没有 progress.evidence 字段。',
            'properties': {
                'set': {'type': 'object', 'properties': progress_fields, 'additionalProperties': True,
                        'description': '替换列出的字段；已知类型如下，其他历史扩展字段可保留 JSON 值。'},
                'append': {'type': 'object', 'properties': list_fields,
                           'additionalProperties': {'type': 'array', 'items': {}},
                           'description': '向列表追加并去重；evidence 是归档 ID 字符串数组。'},
                'remove': {'type': 'object', 'properties': {**list_fields, 'evidence': {'type': 'array', 'items': TEXT}},
                           'additionalProperties': {'type': 'array', 'items': {}},
                           'description': '从列表删除匹配值；不可删空最终 evidence。'}}},
        'knowledge': {'type': 'array', 'maxItems': 20, 'items': entry_schema('knowledge')},
        'tasks': {'type': 'array', 'maxItems': 20, 'items': entry_schema('tasks')},
        'relations': {'type': 'array', 'maxItems': 20, 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['source_id', 'target_id', 'kind', 'reason'],
            'properties': {k: TEXT for k in ('source_id', 'target_id', 'kind', 'reason')}}}
    }
}
# Preserve raw values until aggregate validation; the advertised schema is explicit.
LearningChanges = Annotated[Any, WithJsonSchema(CHANGES_SCHEMA)]
VALIDATOR = Draft202012Validator(CHANGES_SCHEMA)


def validate_changes(c, topic_id, request_id, changes):
    """Collect independent shape/state/evidence errors before any entity write."""
    errors = []

    def issue(path, expected, problem):
        row = dict(path=path, expected=expected, problem=problem)
        if row not in errors: errors.append(row)

    def path(parts):
        return 'changes' + ''.join(f'[{x}]' if isinstance(x, int) else '.' + x for x in parts)

    for e in VALIDATOR.iter_errors(changes):
        p = path(e.absolute_path)
        if e.validator == 'required':
            for key in e.validator_value:
                if key not in e.instance:
                    expected = e.schema.get('properties', {}).get(key, {}).get('type',
                        {'data':'object','title':'string','content':'string','evidence':'非空 string[]',
                         'expected_version':'integer','status':'状态枚举'}.get(key, 'string'))
                    issue(p + '.' + key, expected, '字段缺失')
        elif e.validator == 'additionalProperties' and isinstance(e.instance, dict):
            for key in set(e.instance) - set(e.schema.get('properties', {})):
                issue(p+'.'+key, 'Schema 中列出的字段', '未知字段')
        else:
            expected = e.schema.get('type', str(e.validator_value))
            if e.validator == 'type':
                problem = ('必须是数组；' if expected == 'array' else '') + '实际类型为 ' + type(e.instance).__name__
            else:
                problem = e.message[:240]
            issue(p, str(expected), problem)

    def evidence(refs, p, sources=None):
        if not isinstance(refs, list) or not refs:
            issue(p, '非空 string[]，元素为已归档 messages.id', '必须引用归档消息 ID')
            return
        for i, ref in enumerate(refs):
            if not isinstance(ref, str):
                issue(f'{p}[{i}]', 'string messages.id', '实际类型为 ' + type(ref).__name__)
            else:
                origin = c.execute('SELECT m.conversation_id,v.topic_id,a.conversation_id AS archive_conversation '
                    'FROM messages m JOIN conversations v ON v.id=m.conversation_id '
                    'JOIN archives a ON a.sha256=m.source_hash WHERE m.id=?', (ref,)).fetchone()
                if not origin:
                    issue(f'{p}[{i}]', '已存在的 messages.id', '归档消息不存在')
                    continue
                if origin['archive_conversation'] != origin['conversation_id']:
                    issue(f'{p}[{i}]', '消息与归档来源一致', '归档来源不匹配')
                declared = sources.get(ref) if isinstance(sources, dict) else None
                if declared is not None:
                    if (not isinstance(declared, dict) or
                        declared.get('conversation_id') != origin['conversation_id'] or
                        declared.get('topic_id') != origin['topic_id'] or
                        declared.get('scope') != ('cross_topic' if origin['topic_id'] != topic_id else 'same_topic')):
                        issue(f'{p}[{i}]', '准确的 evidence_sources 来源及 scope', '声明来源与归档不一致')
                elif origin['topic_id'] != topic_id:
                    issue(f'{p}[{i}]', 'evidence_sources 显式 cross_topic 来源', '跨专题证据必须标记来源')

    if isinstance(changes, dict):
        patch = changes.get('progress')
        old = c.execute('SELECT data FROM topic_progress WHERE id=?', (topic_id,)).fetchone()
        if isinstance(patch, dict) and old:
            before = json.loads(old['data']); merged = copy.deepcopy(before)
            setting = patch.get('set', {})
            if isinstance(setting, dict): merged.update(setting)
            for op in ('append', 'remove'):
                values = patch.get(op, {})
                if not isinstance(values, dict): continue
                for key, items in values.items():
                    if not isinstance(items, list): continue
                    target = merged.get(key, [])
                    if not isinstance(target, list):
                        issue(f'changes.progress.{op}.{key}', '目标字段为 array', '合并目标不是数组')
                        continue
                    target = list(target); merged[key] = target
                    for item in items:
                        if op == 'append' and item not in target: target.append(item)
                        if op == 'remove' and item in target: target.remove(item)
            if merged != before:
                supplied = []
                for op in ('set', 'append'):
                    obj = patch.get(op, {})
                    if isinstance(obj, dict) and 'evidence' in obj:
                        evidence(obj['evidence'], f'changes.progress.{op}.evidence', merged.get('evidence_sources'))
                        if isinstance(obj['evidence'], list): supplied.extend(obj['evidence'])
                if not supplied:
                    issue('changes.progress.append.evidence', '非空 string[]，也可在 set.evidence 提供', '进度变更必须引用本次归档消息 ID')
            final_refs = merged.get('evidence')
            if not isinstance(final_refs, list) or not final_refs:
                issue('changes.progress.append.evidence', '合并后 evidence 仍为非空 string[]', '最终进度必须保留归档消息 ID')
            else:
                evidence(final_refs, 'changes.progress.evidence', merged.get('evidence_sources'))
        planned = {}
        for group, table in (('knowledge', 'knowledge_items'), ('tasks', 'learning_tasks')):
            entries = changes.get(group, [])
            if not isinstance(entries, list): continue
            for i, entry in enumerate(entries):
                if not isinstance(entry, dict) or not isinstance(entry.get('data'), dict): continue
                p = f'changes.{group}[{i}]'; data = entry['data']
                ident = entry.get('id'); old = None
                if isinstance(ident, str):
                    old = c.execute(f'SELECT * FROM {table} WHERE id=?', (ident,)).fetchone()
                before = json.loads(old['data']) if old else {}
                merged = dict(before, **data)
                evidence(merged.get('evidence'), p+'.data.evidence', merged.get('evidence_sources'))
                source = merged.get('source_conversation')
                if source is not None:
                    origin = c.execute('SELECT topic_id FROM conversations WHERE id=?', (source,)).fetchone() if isinstance(source, str) else None
                    if not origin or origin['topic_id'] != topic_id:
                        issue(p+'.data.source_conversation', '当前专题内真实来源聊天', '来源聊天不存在或属于其他专题')
                for key in ('title', 'content') if group == 'knowledge' else ('title',):
                    if not isinstance(merged.get(key), str) or not merged[key]:
                        issue(p+'.data.'+key, '非空 string（新建必填；更新可继承）', '缺失或不是非空字符串')
                if old:
                    if old['topic_id'] != topic_id or old['version'] != entry.get('expected_version'):
                        issue(p+'.expected_version', '当前专题实体版本 '+str(old['version']), '实体版本或专题不匹配')
                    if group == 'knowledge':
                        if before.get('claim_key') and (before.get('claim_key'),before.get('claim_value')) != (merged.get('claim_key'),merged.get('claim_value')):
                            issue(p+'.data.claim_value', '与原命题一致', '命题改变须另建条目并关联 conflicts')
                        if before.get('status') in ('verified','reviewed_summary') and before.get('content') != merged.get('content') and not data.get('verification'):
                            issue(p+'.data.verification', '本次可核查验证', '修改已审核结论需要本次 verification 或另建候选')
                if group == 'knowledge': planned[ident if isinstance(ident,str) and ident else digest([group, request_id, i])] = topic_id
                elif merged.get('status') not in ('pending','attempted','completed','unknown'):
                    issue(p+'.data.status', 'pending|attempted|completed|unknown', '缺失或无效状态')
        relations = changes.get('relations', [])
        if isinstance(relations, list):
            for i, rel in enumerate(relations):
                if not isinstance(rel, dict): continue
                tids = []
                for key in ('source_id','target_id'):
                    ident = rel.get(key)
                    if not isinstance(ident, str): continue
                    found = c.execute('SELECT topic_id FROM knowledge_items WHERE id=?', (ident,)).fetchone()
                    tid = found['topic_id'] if found else planned.get(ident)
                    if tid: tids.append(tid)
                    else: issue(f'changes.relations[{i}].{key}', '已有或本批次新增知识 ID', '知识不存在')
                if rel.get('source_id') and rel.get('source_id') == rel.get('target_id'):
                    issue(f'changes.relations[{i}].target_id', '与 source_id 不同', '不能自关联')
                if len(tids) == 2 and topic_id not in tids:
                    issue(f'changes.relations[{i}]', '至少一端属于当前专题', '两端均为其他专题')
    if errors:
        raise KBError('VALIDATION_ERROR', '; '.join(f"{e['path']}: {e['problem']}" for e in errors), errors)
