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


def test_valid_link_retraction_and_duplicate_constraint(tmp_path):
    import sqlite3
    kb=KB(tmp_path/'test.sqlite3')
    with kb.connect() as c:
        c.execute('INSERT INTO c_concepts VALUES(?,?,?,?)', ('c','synthetic','Synthetic',now()))
        c.execute('INSERT INTO c_requests VALUES(?,?,?,?,?)', ('r','hash','test',now(),'{}'))
        c.execute('INSERT INTO c_events(concept_id,version,request_id,kind,data,created_at) VALUES(?,?,?,?,?,?)',('c',1,'r','link','{}',now()))
        concept=c.execute('SELECT * FROM c_concepts').fetchone()
        assert len(project(c,concept)['items'])==1
        c.execute('INSERT INTO c_events(concept_id,version,request_id,kind,data,target_seq,created_at) VALUES(?,?,?,?,?,?,?)',('c',2,'r','retract','{}',1,now()))
        assert project(c,concept)['items']==[]
        with pytest.raises(sqlite3.IntegrityError):
            c.execute('INSERT INTO c_events(concept_id,version,request_id,kind,data,target_seq,created_at) VALUES(?,?,?,?,?,?,?)',('c',3,'r','retract','{}',1,now()))


def test_missing_retract_target_reported(tmp_path):
    kb=KB(tmp_path/'test.sqlite3')
    with kb.connect() as c:
        c.execute('INSERT INTO c_concepts VALUES(?,?,?,?)', ('c','synthetic','Synthetic',now()))
        c.execute('INSERT INTO c_requests VALUES(?,?,?,?,?)', ('r','hash','test',now(),'{}'))
        c.execute('INSERT INTO c_events(concept_id,version,request_id,kind,data,created_at) VALUES(?,?,?,?,?,?)',('c',1,'r','retract','{}',now()))
        with pytest.raises(ReadError,match='INVALID_RETRACTION'):
            project(c,c.execute('SELECT * FROM c_concepts').fetchone())
