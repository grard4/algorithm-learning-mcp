"""Generic topic identity resolution without a publisher's private topic list."""
import hashlib
import unicodedata
from kb import KBError

def norm(text):
    return ' '.join(unicodedata.normalize('NFKC', text).strip().casefold().split())

def resolve(c, name='', canonical='', topic_id=None):
    supplied = [x for x in (name, canonical) if x]
    if any(not isinstance(x, str) for x in supplied):
        raise KBError('INVALID', 'name/canonical 必须是字符串')
    rows = c.execute('SELECT * FROM topics').fetchall()
    candidates = set()
    for value in supplied:
        normalized = norm(value)
        for row in rows:
            if normalized in (norm(row['name']), norm(row['canonical'])):
                candidates.add(row['id'])
    if topic_id:
        if not any(row['id'] == topic_id for row in rows):
            raise KBError('NOT_FOUND', 'topic_id 不存在；不会自动创建专题')
        candidates.add(topic_id)
    if len(candidates) > 1:
        raise KBError('TOPIC_CONFLICT', '专题名称、别名或 topic_id 指向不同专题；请核实范围')
    row = next((row for row in rows if row['id'] in candidates), None)
    explicit = norm(canonical) if canonical else None
    if explicit and row and explicit != norm(row['canonical']):
        raise KBError('TOPIC_CONFLICT', 'canonical 与已有专题或已知别名不一致；不要猜测 canonical')
    if row: return row, row['canonical']
    if not name:
        raise KBError('ASSOCIATION_NOT_FOUND', '尚无聊天关联；请提供明确的新专题 name 或已有 topic_id')
    return None, explicit or 'topic-' + hashlib.sha256(norm(name).encode()).hexdigest()[:20]
