"""发布前隔离契约检查；仅使用 pytest 临时目录。"""
import json
import sqlite3
from pathlib import Path
import pytest
from kb import KB, KBError, now
from context import Context
import preferences
import sync

@pytest.fixture
def prepared(tmp_path):
    kb = KB(tmp_path / "isolated.sqlite3")
    ctx = Context(kb)
    reg = ctx.register("Release Topic", "", "release-chat")
    with kb.connect() as c:
        c.execute("INSERT INTO archives VALUES(?,?,?,?,?,?)", ("fixture-sha", "release-chat", "fixture.jsonl", "synthetic", 10, now()))
        c.execute("INSERT INTO messages VALUES(?,?,?,?,?,?,?,?)", ("fixture-message", "release-chat", 1, "user", now(), "Synthetic evidence", "fixture-sha", 1))
    return kb, ctx, reg["topic_id"]

def snapshot(kb):
    with kb.connect() as c:
        names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        return {name: sorted([tuple(r) for r in c.execute('SELECT * FROM "' + name + '"')], key=repr) for name in names}

def changes():
    return {"progress": {"append": {"taught": ["synthetic range sum"], "evidence": ["fixture-message"]}},
            "knowledge": [{"data": {"title": "Synthetic aggregation", "content": "Synthetic range aggregation evidence.", "evidence": ["fixture-message"]}}]}

def test_aggregate_validation_and_no_partial_data(prepared):
    kb, ctx, topic = prepared
    before = snapshot(kb)
    with pytest.raises(KBError) as caught:
        ctx.update(topic, "release-chat", ctx.version(topic)["topic_version"], "bad-shape", {
            "progress": {"append": {"taught": "not-an-array"}}, "knowledge": [{"data": {}}]})
    assert caught.value.code == "VALIDATION_ERROR"
    detail = json.dumps(caught.value.details)
    for key in ["progress.append.taught", "knowledge[0].data.title", "knowledge[0].data.content", "knowledge[0].data.evidence"]:
        assert key in detail
    assert snapshot(kb) == before

def test_missing_evidence_rejected(prepared):
    kb, ctx, topic = prepared
    before = snapshot(kb)
    with pytest.raises(KBError):
        ctx.update(topic, "release-chat", ctx.version(topic)["topic_version"], "no-evidence", {"progress": {"set": {"stage": "new"}}})
    assert snapshot(kb) == before

def test_update_replay_conflict_and_persistence(prepared):
    kb, ctx, topic = prepared
    version = ctx.version(topic)["topic_version"]
    first = ctx.update(topic, "release-chat", version, "once", changes())
    after = snapshot(kb)
    assert ctx.update(topic, "release-chat", version, "once", changes()) == first
    assert snapshot(kb) == after
    with pytest.raises(KBError) as caught:
        ctx.update(topic, "release-chat", version, "once", {})
    assert caught.value.code == "IDEMPOTENCY_CONFLICT"
    with pytest.raises(KBError) as caught:
        ctx.update(topic, "release-chat", version, "stale", changes())
    assert caught.value.code == "VERSION_CONFLICT"
    reopened = KB(kb.path)
    assert snapshot(reopened) == after
    assert reopened.rows("PRAGMA foreign_key_check") == []
    assert reopened.search("aggregation")

def test_mid_transaction_failure_rolls_back(prepared, monkeypatch):
    kb, ctx, topic = prepared
    before = snapshot(kb)
    original = kb.change
    calls = []
    def fail_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise sqlite3.IntegrityError("injected foreign key failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(kb, "change", fail_second)
    with pytest.raises(sqlite3.IntegrityError):
        ctx.update(topic, "release-chat", ctx.version(topic)["topic_version"], "atomic-failure", changes())
    assert len(calls) == 2
    assert snapshot(kb) == before
    assert kb.rows("PRAGMA integrity_check")[0]["integrity_check"] == "ok"

def test_existing_mapping_reuse_and_conflict(prepared):
    kb, ctx, topic = prepared
    before = snapshot(kb)
    assert ctx.register("", "", "release-chat")["topic_id"] == topic
    assert snapshot(kb) == before
    with pytest.raises(KBError) as caught:
        ctx.register("Unrelated course", "", "release-chat")
    assert caught.value.code == "TOPIC_CONFLICT"
    assert snapshot(kb) == before
    assert ctx.register("Second topic", "", "second-chat")["topic_id"] != topic

def test_preference_size_boundary(tmp_path, monkeypatch):
    path = tmp_path / "preferences.md"
    monkeypatch.setenv("ALGORITHM_PREFERENCES", str(path))
    path.write_bytes(b"x" * preferences.MAX_BYTES)
    assert preferences.read_preferences()["status"] == "custom"
    path.write_bytes(b"x" * (preferences.MAX_BYTES + 1))
    result = preferences.read_preferences()
    assert result["status"] == "invalid" and "text" not in result
    path.write_text("", encoding="utf-8")
    assert preferences.read_preferences()["status"] == "empty"

def test_unselected_rollout_is_not_imported(tmp_path):
    kb = KB(tmp_path / "import.sqlite3")
    rollout = tmp_path / "rollout-synthetic.jsonl"
    rollout.write_text(json.dumps({"type": "session_meta", "payload": {"id": "unselected-test-chat"}}) + "\n", encoding="utf-8")
    before = snapshot(kb)
    assert sync.sync_file(kb, rollout, allow_new=False) == {"ignored": "unselected-test-chat"}
    assert snapshot(kb) == before
    assert not (tmp_path / "archives").exists()

def test_base_schema_upgrade_preserves_existing_topic(tmp_path):
    path = tmp_path / "old.sqlite3"
    with sqlite3.connect(path) as c:
        c.executescript((Path(__file__).resolve().parents[1] / "schema.sql").read_text(encoding="utf-8"))
        c.execute("INSERT INTO topics VALUES(?,?,?,?,?)", ("old-topic", "Synthetic old topic", "old-topic", None, now()))
    kb = KB(path)
    assert kb.rows("SELECT name FROM topics WHERE id='old-topic'")[0]["name"] == "Synthetic old topic"
    assert kb.rows("SELECT count(*) AS n FROM c_concepts")[0]["n"] == 0
    assert kb.rows("PRAGMA foreign_key_check") == []
    before = snapshot(kb)
    assert snapshot(KB(path)) == before
