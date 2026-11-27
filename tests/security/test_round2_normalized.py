import importlib
import pytest
from kb import KB
import input_limits as lim

@pytest.fixture
def service(tmp_path,monkeypatch):
    s=importlib.import_module('server');k=KB(tmp_path/'db.sqlite3')
    monkeypatch.setattr(s,'kb',k);k.register('Test','','chat','Test')
    return s,k

def msg(content='x',stamp='2026-11-27T00:00:00Z'):
    return dict(role='user',content=content,timestamp=stamp)

def snapshot(k):
    with k.connect() as c: tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '%_fts%'")]
    return {t:k.rows('SELECT * FROM "'+t+'"') for t in tables},set(k.path.parent.rglob('*.normalized.json'))

@pytest.mark.parametrize('kind',['empty','count','bytes','multibyte','total','escaped_total','nested','identifier','timestamp'])
def test_rejected_input_is_atomic(service,kind,monkeypatch):
    s,k=service;messages=[msg()];cid='chat'
    if kind=='empty':messages=[]
    elif kind=='count':messages=[msg()]*(lim.NORMALIZED_MESSAGES+1)
    elif kind=='bytes':messages=[msg('a'*(lim.MESSAGE_BYTES+1))]
    elif kind=='multibyte':messages=[msg('中'*(lim.MESSAGE_BYTES//3+1))]
    elif kind=='total':messages=[msg('a'*lim.MESSAGE_BYTES)]*8
    elif kind=='escaped_total':messages=[msg('\x00'*lim.MESSAGE_BYTES)]*2
    elif kind=='nested':
        nested=[]
        for _ in range(2000):nested=[nested]
        messages[0]['extra']=nested
    elif kind=='identifier':cid='x'*(lim.IDENTIFIER_BYTES+1)
    else:messages=[msg(stamp='2026-02-30T00:00:00Z')]
    before=snapshot(k)
    assert not s.record_conversation_update(cid,messages,'bad')['ok']
    assert snapshot(k)==before

@pytest.mark.parametrize('stamp',['','time','2026-01-01','2026-01-01T00:00:00','0000-01-01T00:00:00Z','2026-01-01T00:00:60Z','2026-01-01T00:00:00+00:60','2026-01-01T00:00:00+24:00'])
def test_invalid_timestamps(stamp):
    with pytest.raises(Exception):lim.timestamp(stamp)

def test_valid_boundaries_and_idempotency(service):
    s,k=service
    for i,messages in enumerate(([msg('中'*(lim.MESSAGE_BYTES//3)+'a')],[msg()]*lim.NORMALIZED_MESSAGES)):
        result=s.record_conversation_update('chat',messages,str(i))
        assert result['ok']
        assert s.record_conversation_update('chat',messages,str(i))==result

def test_exact_serialized_request_boundary(monkeypatch):
    from kb import dump
    m=[msg()]
    n=len((dump(dict(kind='normalized-import',conversation_id='chat',messages=m,request_id='r',actor='a'))+'\n').encode())
    monkeypatch.setattr(lim,'REQUEST_BYTES',n)
    assert lim.normalized_raw('chat',m,'r','a')
    monkeypatch.setattr(lim,'REQUEST_BYTES',n-1)
    with pytest.raises(Exception):lim.normalized_raw('chat',m,'r','a')

def test_publish_failure_rolls_back(service,monkeypatch):
    s,k=service;before=snapshot(k)
    def fail(*a):raise PermissionError('synthetic')
    monkeypatch.setattr(s,'publish',fail)
    assert not s.record_conversation_update('chat',[msg()],'failure')['ok']
    assert snapshot(k)==before
