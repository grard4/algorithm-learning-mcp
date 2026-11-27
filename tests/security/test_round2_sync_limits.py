import json
import pytest
import zstandard
import sync
import input_limits as lim
from kb import KB, KBError

def raw(text='proof',count=1):
    events=[{'type':'session_meta','payload':{'id':'chat'}}]
    events += [{'type':'response_item','timestamp':'2026-11-27T00:00:00Z','payload':{'type':'message','role':'user','content':[{'type':'text','text':text}]}}]*count
    return ('\n'.join(json.dumps(x) for x in events)+'\n').encode()

@pytest.mark.parametrize('case',['source','decoded','ratio','events','line','message','depth','nodes','truncated','corrupt','timestamp'])
def test_limits_preserve_state_and_retry(tmp_path,monkeypatch,case):
    k=KB(tmp_path/'db.sqlite3');p=tmp_path/'source.jsonl';p.write_bytes(raw())
    sync.sync_file(k,p,name='Test')
    before=(k.rows('SELECT * FROM sync_state'),k.rows('SELECT * FROM messages'),set(k.path.parent.rglob('*.jsonl')))
    with monkeypatch.context() as m:
        if case=='source':m.setattr(lim,'SOURCE_BYTES',10)
        elif case=='decoded':
            p=p.with_suffix('.zst');p.write_bytes(zstandard.ZstdCompressor().compress(raw('proof'*100)))
            m.setattr(lim,'DECOMPRESSED_BYTES',100)
        elif case=='ratio':
            p=p.with_suffix('.zst');p.write_bytes(zstandard.ZstdCompressor().compress(raw('a'*10000)))
            m.setattr(lim,'RATIO_ALLOWANCE',100);m.setattr(lim,'COMPRESSION_RATIO',2)
        elif case=='events':p.write_bytes(raw(count=3));m.setattr(lim,'EVENTS',2)
        elif case=='line':m.setattr(lim,'LINE_BYTES',20)
        elif case=='message':p.write_bytes(raw('x'*101));m.setattr(lim,'MESSAGE_BYTES',100)
        elif case=='depth':p.write_bytes(b'{"type":"session_meta","payload":{"id":"chat","x":'+b'['*40+b'0'+b']'*40+b'}}\n')
        elif case=='nodes':m.setattr(lim,'JSON_NODES',5)
        elif case=='timestamp':p.write_bytes(raw().replace(b'2026-11-27T00:00:00Z',b'invalid'))
        elif case=='truncated':p=p.with_suffix('.zst');p.write_bytes(zstandard.ZstdCompressor().compress(raw())[:-1])
        else:p=p.with_suffix('.zst');p.write_bytes(b'corrupt')
        with pytest.raises(KBError):sync.sync_file(k,p)
        assert k.rows('SELECT * FROM sync_state')==before[0]
        assert k.rows('SELECT * FROM messages')==before[1]
        assert set(k.path.parent.rglob('archives/**/*.jsonl'))=={x for x in before[2] if 'archives' in x.parts}
    p=tmp_path/'source.jsonl';p.write_bytes(raw(count=2))
    assert sync.sync_file(k,p)['imported']==1
    assert sync.sync_file(k,p)['unchanged']

def test_multiframe_and_exact_source_boundary(tmp_path,monkeypatch):
    p=tmp_path/'source.zst';data=raw()
    p.write_bytes(zstandard.ZstdCompressor().compress(data)+zstandard.ZstdCompressor().compress(data))
    monkeypatch.setattr(lim,'SOURCE_BYTES',p.stat().st_size)
    assert sync.read_bytes(p)==data+data
    monkeypatch.setattr(lim,'SOURCE_BYTES',p.stat().st_size-1)
    with pytest.raises(KBError):sync.read_bytes(p)

def test_changed_source_does_not_publish_or_advance(tmp_path):
    k=KB(tmp_path/'db.sqlite3');p=tmp_path/'source.jsonl';p.write_bytes(raw())
    sync.sync_file(k,p,name='Test')
    before=set(k.path.parent.rglob('archives/**/*.jsonl'))
    p.write_bytes(raw('changed'))
    with pytest.raises(KBError):sync.sync_file(k,p)
    assert set(k.path.parent.rglob('archives/**/*.jsonl'))==before

def test_window_budget(tmp_path):
    params=zstandard.ZstdCompressionParameters.from_level(3,window_log=24,write_content_size=0)
    compressor=zstandard.ZstdCompressor(compression_params=params).compressobj()
    compressed=compressor.compress(raw())+compressor.flush()
    assert zstandard.get_frame_parameters(compressed).window_size>lim.WINDOW_BYTES
    path=tmp_path/'large-window.zst';path.write_bytes(compressed)
    with pytest.raises(KBError):sync.read_bytes(path)

def test_frame_count_budget(tmp_path,monkeypatch):
    frame=zstandard.ZstdCompressor().compress(b'')
    p=tmp_path/'frames.zst';p.write_bytes(frame*4)
    monkeypatch.setattr(lim,'EVENTS',3)
    with pytest.raises(KBError):sync.read_bytes(p)

def test_exact_decoded_event_and_message_boundaries(tmp_path,monkeypatch):
    data=raw('中'*100);p=tmp_path/'bounded.zst'
    p.write_bytes(zstandard.ZstdCompressor().compress(data))
    monkeypatch.setattr(lim,'DECOMPRESSED_BYTES',len(data))
    monkeypatch.setattr(lim,'EVENTS',2)
    monkeypatch.setattr(lim,'MESSAGE_BYTES',300)
    assert sync.visible(sync.parse(sync.read_bytes(p)))[0]['content']=='中'*100
    monkeypatch.setattr(lim,'DECOMPRESSED_BYTES',len(data)-1)
    with pytest.raises(KBError):sync.read_bytes(p)
