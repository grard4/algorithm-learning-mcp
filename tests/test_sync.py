import sync

def test_discovery_cutoff_is_persisted_once(tmp_path, monkeypatch):
    monkeypatch.setattr(sync,"ROOT",tmp_path)
    values=iter([1000.0,2000.0])
    monkeypatch.setattr(sync.time,"time",lambda: next(values))
    first=sync.discovery_cutoff()
    second=sync.discovery_cutoff()
    assert first==1000.0
    assert second==first
    assert (tmp_path/"config"/"discovery_since.txt").read_text()=="1000.0"

def test_invalid_discovery_cutoff_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(sync,"ROOT",tmp_path)
    p=tmp_path/"config"/"discovery_since.txt"
    p.parent.mkdir();p.write_text("not-a-time")
    try:
        sync.discovery_cutoff()
    except Exception as exc:
        assert getattr(exc,"code",None)=="INVALID_DISCOVERY_CUTOFF"
    else:
        raise AssertionError("invalid persistent cutoff must fail closed")
