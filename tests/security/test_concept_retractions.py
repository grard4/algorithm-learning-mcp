import pytest
from kb import KB, now
from concept_reader import project, ReadError


@pytest.mark.parametrize('target_kind', ['create','alias','retract'])
def test_retract_non_link_fails_closed(tmp_path, target_kind):
    kb=KB(tmp_path/'test.sqlite3')
    with kb.connect() as c:
        c.execute('INSERT INTO c_concepts VALUES(?,?,?,?)', ('c','synthetic','Synthetic',now()))
        c.execute('INSERT INTO c_requests VALUES(?,?,?,?,?)', ('r','hash','test',now(),'{}'))
        c.execute('INSERT INTO c_events(concept_id,version,request_id,kind,data,created_at) VALUES(?,?,?,?,?,?)',('c',1,'r',target_kind,'{}',now()))
        c.execute('INSERT INTO c_events(concept_id,version,request_id,kind,data,target_seq,created_at) VALUES(?,?,?,?,?,?,?)',('c',2,'r','retract','{}',1,now()))
        with pytest.raises(ReadError, match='INVALID_RETRACTION'):
            project(c,c.execute('SELECT * FROM c_concepts').fetchone())
    assert kb.rows('PRAGMA foreign_key_check')==[]
