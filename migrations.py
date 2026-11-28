"""Small, atomic ledger for the existing additive schema bundle."""
import hashlib
import sqlite3

SYNC_SOURCES_SQL="""CREATE TABLE sync_sources(
 conversation_id TEXT NOT NULL REFERENCES conversations(id),
 source_key TEXT NOT NULL,
 source_path TEXT NOT NULL,
 source_hash TEXT NOT NULL REFERENCES archives(sha256),
 line_count INTEGER NOT NULL CHECK(line_count>0),
 seq_offset INTEGER NOT NULL CHECK(seq_offset>=0),
 updated_at TEXT NOT NULL,
 PRIMARY KEY(conversation_id,source_key),
 UNIQUE(conversation_id,seq_offset)
)"""


def statements(script):
    pending=''
    for char in script:
        pending+=char
        if char==';' and sqlite3.complete_statement(pending):
            yield pending
            pending=''
    if pending.strip():
        # A trailing comment is harmless, but SQL without a terminator is not.
        if any(line.strip() and not line.lstrip().startswith('--') for line in pending.splitlines()):
            raise ValueError('unterminated migration SQL')


def initialize(c, root):
    from kb import KBError, now
    import notifications
    scripts=[(root/name).read_text(encoding='utf-8') for name in
             ('schema.sql','context_schema.sql','c_context_schema.sql')]
    checksum=hashlib.sha256('\n'.join(scripts).encode()).hexdigest()
    c.execute('BEGIN IMMEDIATE')
    if c.execute('PRAGMA user_version').fetchone()[0]!=0:
        raise KBError('UNKNOWN_SCHEMA_VERSION','未知数据库版本；拒绝自动迁移')
    exists=c.execute("SELECT 1 FROM sqlite_master WHERE name='schema_migrations'").fetchone()
    source_table_exists=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sync_sources'").fetchone()
    if exists:
        rows=[tuple(r) for r in c.execute('SELECT name,sha256 FROM schema_migrations ORDER BY rowid')]
        if not rows or rows[0]!=('core-v1',checksum) or rows not in (
            [('core-v1',checksum)],
            [('core-v1',checksum),('sync-sources-v1',hashlib.sha256(SYNC_SOURCES_SQL.encode()).hexdigest())]
        ):
            raise KBError('MIGRATION_CHECKSUM','迁移版本或 checksum 不匹配')
        if bool(source_table_exists)!=(len(rows)==2):
            raise KBError('MIGRATION_CHECKSUM','分片同步迁移记录与数据库结构不一致')
    elif source_table_exists:
        raise KBError('MIGRATION_CHECKSUM','分片同步表缺少迁移记录')
    # Validate legacy structural shape before adopting it; never silently mask drift.
    expected=sqlite3.connect(':memory:')
    try:
        expected.executescript('\n'.join(scripts))
        for name, sql in expected.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'"):
            actual=c.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()
            if actual and ' '.join(actual[0].split()) != ' '.join(sql.split()):
                raise KBError('SCHEMA_DRIFT','已有 SQL 定义不兼容：'+name)
        for name, in expected.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            if not c.execute('SELECT 1 FROM sqlite_master WHERE type=\'table\' AND name=?',(name,)).fetchone():
                continue
            quoted='"'+name.replace('"','""')+'"'
            for pragma in ('table_info','foreign_key_list'):
                actual=[tuple(r) for r in c.execute(f'PRAGMA {pragma}({quoted})')]
                wanted=list(expected.execute(f'PRAGMA {pragma}({quoted})'))
                if actual!=wanted:
                    raise KBError('SCHEMA_DRIFT','已有表结构不兼容：'+name)
    finally:
        expected.close()
    for script in scripts:
        for statement in statements(script): c.execute(statement)
    notifications.install_transaction(c)
    c.execute('CREATE TABLE IF NOT EXISTS schema_migrations(name TEXT PRIMARY KEY,sha256 TEXT NOT NULL,applied_at TEXT NOT NULL)')
    c.execute('INSERT OR IGNORE INTO schema_migrations VALUES(?,?,?)',('core-v1',checksum,now()))
    source_checksum=hashlib.sha256(SYNC_SOURCES_SQL.encode()).hexdigest()
    if not source_table_exists:
        c.execute(SYNC_SOURCES_SQL)
        from sync_identity import source_key
        states=c.execute('''SELECT s.conversation_id,s.source_hash,s.line_count,a.source_path,a.sha256 archive_hash
                            FROM sync_state s LEFT JOIN archives a
                            ON a.conversation_id=s.conversation_id AND a.sha256=s.source_hash
                            ORDER BY s.conversation_id''').fetchall()
        for state in states:
            if state['archive_hash']!=state['source_hash']:
                raise KBError('SYNC_MIGRATION_UNSAFE','已有同步游标缺少匹配的内容寻址归档')
            source_path=state['source_path']
            if not source_path:
                source_path=c.execute('SELECT source_path FROM conversations WHERE id=?',(state['conversation_id'],)).fetchone()[0]
            if not source_path or not state['line_count'] or state['line_count']<1:
                raise KBError('SYNC_MIGRATION_UNSAFE','已有同步游标缺少可验证的来源信息')
            offsets=[r[0] for r in c.execute('SELECT DISTINCT seq-source_line FROM messages WHERE conversation_id=? AND seq>0',(state['conversation_id'],))]
            if len(offsets)>1 or (offsets and offsets[0]<0):
                raise KBError('SYNC_MIGRATION_UNSAFE','已有消息序号不能安全映射到 rollout 分片')
            max_line=c.execute('SELECT MAX(source_line) FROM messages WHERE conversation_id=? AND seq>0',(state['conversation_id'],)).fetchone()[0]
            if max_line is not None and max_line>state['line_count']:
                raise KBError('SYNC_MIGRATION_UNSAFE','已有消息行号超出同步游标')
            try:
                key=source_key(source_path)
            except ValueError as exc:
                raise KBError('SYNC_MIGRATION_UNSAFE','已有同步来源标识无效') from exc
            c.execute('INSERT INTO sync_sources VALUES(?,?,?,?,?,?,?)',(
                state['conversation_id'],key,source_path,state['source_hash'],state['line_count'],offsets[0] if offsets else 0,now()))
    else:
        actual=c.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sync_sources'").fetchone()
        if not actual or ' '.join(actual[0].split())!=' '.join(SYNC_SOURCES_SQL.split()):
            raise KBError('SCHEMA_DRIFT','分片同步表结构不兼容')
    c.execute('INSERT OR IGNORE INTO schema_migrations VALUES(?,?,?)',('sync-sources-v1',source_checksum,now()))
