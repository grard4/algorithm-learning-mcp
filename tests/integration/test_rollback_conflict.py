import pytest
from kb import KBError


def test_rollback_conflicts_and_latest_rollback(linked):
    kb,ctx,tid=linked
    first=kb.write('knowledge_items','k',{'title':'first','content':'first'},'edit-1','test',expected_version=1)
    second=kb.write('knowledge_items','k',{'title':'second','content':'second'},'edit-2','test',expected_version=2)
    with pytest.raises(KBError) as caught:kb.rollback(first['update_id'],'rollback-old','test')
    assert caught.value.code=='ROLLBACK_CONFLICT'
    assert kb.get('knowledge_items','k')['data']['content']=='second'
    kb.rollback(second['update_id'],'rollback-latest','test')
    assert kb.get('knowledge_items','k')['data']['content']=='first'
    assert kb.get('knowledge_items','k')['version']==4
