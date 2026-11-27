-- Additive migration; original records and audit history remain intact.
CREATE TABLE IF NOT EXISTS context_events(
 change_id INTEGER NOT NULL REFERENCES change_history(id),
 topic_id TEXT NOT NULL REFERENCES topics(id),
 entity TEXT NOT NULL, entity_id TEXT NOT NULL,
 PRIMARY KEY(change_id,topic_id)
);
CREATE INDEX IF NOT EXISTS ix_context_topic ON context_events(topic_id,change_id);
CREATE VIEW IF NOT EXISTS context_event_source AS
 SELECT h.id change_id,
 CASE WHEN h.entity IN ('topics','topic_progress') THEN h.entity_id
 ELSE json_extract(COALESCE(h.after_json,h.before_json),'$.topic_id') END topic_id,
 h.entity,h.entity_id FROM change_history h
 WHERE h.entity IN ('topics','topic_progress','knowledge_items','learning_tasks','conversations','conversation_tree')
 AND (h.entity<>'topic_progress' OR h.before_json IS NULL OR h.after_json IS NULL OR
 json_remove(json_extract(h.before_json,'$.data'),'$.recent_activity') <>
 json_remove(json_extract(h.after_json,'$.data'),'$.recent_activity'))
 UNION
 SELECT h.id,k.topic_id,h.entity,h.entity_id FROM change_history h JOIN knowledge_items k
 ON k.id IN (json_extract(COALESCE(h.after_json,h.before_json),'$.source_id'),
 json_extract(COALESCE(h.after_json,h.before_json),'$.target_id'))
 WHERE h.entity='knowledge_relations';
CREATE TRIGGER IF NOT EXISTS context_history_insert AFTER INSERT ON change_history BEGIN
 INSERT OR IGNORE INTO context_events SELECT s.* FROM context_event_source s
 JOIN topics t ON t.id=s.topic_id WHERE s.change_id=new.id;
END;
CREATE TABLE IF NOT EXISTS context_migrations(name TEXT PRIMARY KEY);
INSERT OR IGNORE INTO context_events
 SELECT s.* FROM context_event_source s JOIN topics t ON t.id=s.topic_id
 WHERE NOT EXISTS(SELECT 1 FROM context_migrations WHERE name='events-v1');
INSERT OR IGNORE INTO context_migrations VALUES('events-v1');
CREATE TABLE IF NOT EXISTS extraction_seen(
 message_id TEXT PRIMARY KEY REFERENCES messages(id), processed_at TEXT NOT NULL
);
INSERT OR IGNORE INTO extraction_seen
 SELECT m.id,COALESCE(m.timestamp,'') FROM messages m
 JOIN knowledge_items k ON json_extract(k.data,'$.evidence[0]')=m.id
 WHERE NOT EXISTS(SELECT 1 FROM context_migrations WHERE name='extraction-v2');
INSERT OR IGNORE INTO context_migrations VALUES('extraction-v2');
CREATE INDEX IF NOT EXISTS ix_knowledge_content_hash ON knowledge_items(json_extract(data,'$.content_hash'));
