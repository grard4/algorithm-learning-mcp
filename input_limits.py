"""Central, non-configurable resource budgets for untrusted archive inputs."""
import json
import re
from datetime import datetime
from typing import Annotated, Any
from pydantic import WithJsonSchema
from kb import KBError, dump

MESSAGE_BYTES = 256 * 1024
NORMALIZED_MESSAGES = 128
REQUEST_BYTES = 2 * 1024 * 1024
IDENTIFIER_BYTES = 512
SOURCE_BYTES = 16 * 1024 * 1024
DECOMPRESSED_BYTES = 32 * 1024 * 1024
WINDOW_BYTES = 8 * 1024 * 1024
COMPRESSION_RATIO = 200
RATIO_ALLOWANCE = 1024 * 1024
EVENTS = 20000
LINE_BYTES = 1024 * 1024
JSON_DEPTH = 32
JSON_NODES = 250000
CHUNK_BYTES = 64 * 1024

TIMESTAMP_PATTERN = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$'
NORMALIZED_SCHEMA = {'type':'array','minItems':1,'maxItems':NORMALIZED_MESSAGES,
    'description':'Strict messages; each content <=256 KiB UTF-8, total request <=2 MiB serialized UTF-8.',
    'items':{'type':'object','additionalProperties':False,'required':['role','content','timestamp'],
        'properties':{'role':{'enum':['user','assistant']},
            'content':{'type':'string','minLength':1,'maxLength':MESSAGE_BYTES},
            'timestamp':{'type':'string','maxLength':32,'pattern':TIMESTAMP_PATTERN}}}}
NormalizedMessages = Annotated[Any, WithJsonSchema(NORMALIZED_SCHEMA)]


def too_large(message):
    raise KBError('TOO_LARGE', message)


def utf8_size(value, maximum, field):
    if not isinstance(value,str):
        raise KBError('INVALID_INPUT',field+' 必须是文本')
    if len(value)>maximum: too_large(field+' 超过字节预算')
    try: size=len(value.encode('utf-8'))
    except UnicodeEncodeError as exc:
        raise KBError('INVALID_INPUT',field+' 含非法 Unicode') from exc
    if size>maximum: too_large(field+' 超过 UTF-8 字节预算')
    return size


def timestamp(value):
    if not isinstance(value,str) or len(value)>32 or not re.fullmatch(TIMESTAMP_PATTERN,value):
        raise KBError('INVALID_TIMESTAMP','timestamp 需带时区的 RFC3339 日期时间（最多六位小数秒）')
    try:
        # datetime rejects impossible dates, years, leap seconds and offsets >=24h.
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        offset=value[-6:] if not value.endswith('Z') else None
        if offset and (int(offset[1:3])>23 or int(offset[4:6])>59): raise ValueError('offset')
        if parsed.tzinfo is None: raise ValueError('timezone')
    except ValueError as exc:
        raise KBError('INVALID_TIMESTAMP','timestamp 的日期、时间或时区无效') from exc


def normalized_raw(conversation_id,messages,request_id,actor):
    for name,value in (('conversation_id',conversation_id),('request_id',request_id),('actor',actor)):
        if not value: raise KBError('INVALID_INPUT',name+' 不能为空')
        utf8_size(value,IDENTIFIER_BYTES,name)
    if not isinstance(messages,list) or not messages:
        raise KBError('INVALID_INPUT','messages 必须是非空数组')
    if len(messages)>NORMALIZED_MESSAGES: too_large('messages 超过数量预算')
    # Reject unknown/nested members before any recursive serializer is invoked.
    for m in messages:
        if not isinstance(m,dict) or set(m)!={'role','content','timestamp'}:
            raise KBError('INVALID_INPUT','每条消息仅允许 role/content/timestamp')
        if m['role'] not in ('user','assistant') or not isinstance(m['content'],str) or not m['content']:
            raise KBError('INVALID_INPUT','消息角色或正文无效')
        utf8_size(m['content'],MESSAGE_BYTES,'content')
        timestamp(m['timestamp'])
    base={'kind':'normalized-import','conversation_id':conversation_id,'messages':[]}
    # Count the canonical serialized request, including escapes and caller metadata,
    # one bounded message at a time, before serializing the whole batch.
    total=len((dump(dict(base,request_id=request_id,actor=actor))+'\n').encode())
    for i,m in enumerate(messages):
        total+=len(dump(m).encode())+(2 if i else 0)
        if total>REQUEST_BYTES: too_large('请求超过序列化 UTF-8 字节预算')
    return (dump(dict(base,messages=messages))+'\n').encode()


def check_json_depth(raw):
    """Scan bytes before json.loads; braces in strings and escaped quotes are ignored."""
    depth=0;quoted=False;escaped=False
    for ch in raw:
        if quoted:
            if escaped: escaped=False
            elif ch==92: escaped=True
            elif ch==34: quoted=False
        elif ch==34: quoted=True
        elif ch in (91,123):
            depth+=1
            if depth>JSON_DEPTH: too_large('JSON 嵌套超过深度预算')
        elif ch in (93,125): depth-=1


def count_nodes(value,remaining):
    stack=[value];used=0
    while stack:
        item=stack.pop();used+=1
        if used>remaining: too_large('JSON 节点超过预算')
        if isinstance(item,dict):
            used+=len(item)  # keys also occupy memory
            if used+len(stack)+len(item)>remaining: too_large('JSON 节点超过预算')
            stack.extend(item.values())
        elif isinstance(item,list):
            if used+len(stack)+len(item)>remaining: too_large('JSON 节点超过预算')
            stack.extend(item)
    return used
