from concurrent.futures import ThreadPoolExecutor
from kb import KB

def test_blank_database_and_r3_journal(tmp_path):
    kb=KB(tmp_path/"empty.sqlite3")
    assert kb.topics()==[]
    with kb.connect() as c:
        assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"
        assert c.execute("SELECT count(*) FROM c_concepts").fetchone()[0]==0
        assert c.execute("SELECT count(*) FROM c_events").fetchone()[0]==0
        assert c.execute("SELECT rule FROM r3_meta WHERE singleton=1").fetchone()[0]=="c23-invalidation-r3-v1"

def test_concurrent_independent_topic_writes(tmp_path):
    path=tmp_path/"shared.sqlite3"
    KB(path)
    def register(i):
        return KB(path).register(f"Topic {i}","",f"conversation-{i}",f"Course {i}")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results=list(pool.map(register,range(20)))
    assert len({x['topic_id'] for x in results})==20
    assert len(KB(path).topics())==20
    assert KB(path).rows("PRAGMA integrity_check")[0]['integrity_check']=="ok"


def test_registration_idempotency_and_backup_restore(tmp_path):
    path=tmp_path/"source.sqlite3"
    kb=KB(path)
    first=kb.register("Geometry Course","","chat-geometry","Geometry")
    second=kb.register("Geometry Course","","chat-geometry","Geometry")
    assert first==second
    backup=tmp_path/"backup.sqlite3"
    kb.backup(backup)
    restored=KB(backup,initialize=False)
    assert restored.rows("PRAGMA integrity_check")[0]['integrity_check']=="ok"
    assert len(restored.topics())==1
