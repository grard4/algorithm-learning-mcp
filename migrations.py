"""Small, atomic ledger for the existing additive schema bundle."""
import hashlib
import sqlite3


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
    if exists:
        rows=[tuple(r) for r in c.execute('SELECT name,sha256 FROM schema_migrations')]
        if rows!=[('core-v1',checksum)]:
            raise KBError('MIGRATION_CHECKSUM','迁移版本或 checksum 不匹配')
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
