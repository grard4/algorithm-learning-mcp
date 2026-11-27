from preferences import DEFAULT_TEXT, read_preferences

def test_missing_empty_invalid_and_reload(tmp_path, monkeypatch):
    p=tmp_path/"prefs.md"
    monkeypatch.setenv("ALGORITHM_PREFERENCES",str(p))
    assert read_preferences()["status"]=="missing"
    assert read_preferences()["text"]==DEFAULT_TEXT
    p.write_text("first",encoding="utf-8")
    assert read_preferences()["text"]=="first"
    p.write_text("second preference",encoding="utf-8")
    assert read_preferences()["text"]=="second preference"
    p.write_bytes(b"\xff")
    assert read_preferences()["status"]=="invalid"
    p.unlink()
    assert read_preferences()["status"]=="missing"
