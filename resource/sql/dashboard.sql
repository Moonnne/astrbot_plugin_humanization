-- name: sessions
SELECT scope FROM sessions UNION SELECT scope FROM diary_days
UNION SELECT scope FROM controller_decisions ORDER BY scope;

-- name: stats
SELECT
 (SELECT COUNT(*) FROM sessions WHERE :scope='' OR scope=:scope) AS sessions,
 (SELECT COUNT(*) FROM messages WHERE :scope='' OR scope=:scope) AS messages,
 (SELECT COUNT(*) FROM diary_topics WHERE :scope='' OR scope=:scope) AS topics,
 (SELECT COUNT(*) FROM diary_days WHERE :scope='' OR scope=:scope) AS diaries,
 (SELECT COUNT(*) FROM controller_decisions WHERE :scope='' OR scope=:scope) AS decisions,
 (SELECT COUNT(*) FROM controller_decisions WHERE (:scope='' OR scope=:scope)
   AND json_extract(decision_json,'$.reply')=1) AS planned_replies,
 (SELECT COUNT(*) FROM controller_decisions WHERE (:scope='' OR scope=:scope)
   AND outcome='processed') AS processed;

-- name: messages
SELECT *, sent_at AS timestamp, text AS headline, direction AS kind,
 sender_name || ' ' || sender_id || ' ' || message_id || ' ' || text AS search
FROM messages

-- name: decisions
SELECT *, created_at AS timestamp, observed_through_seq AS seq,
 date(created_at,'unixepoch',:offset) AS day, outcome AS kind,
 json_extract(decision_json,'$.reason') AS headline, decision_json AS search
FROM controller_decisions

-- name: topics
SELECT *, topic_at AS timestamp, first_seq AS seq, topic AS headline,
 '' AS kind, topic || ' ' || interact || ' ' || reply || ' ' || reaction AS search
FROM diary_topics

-- name: diaries
SELECT d.*, d.day AS id, d.updated_at AS timestamp, d.through_seq AS seq,
 d.day AS headline, CAST(d.sealed AS TEXT) AS kind,
 COALESCE((SELECT group_concat(topic || ' ' || interact || ' ' || reply || ' ' || reaction,' ')
 FROM diary_topics t WHERE t.scope=d.scope AND t.day=d.day),'') AS search,
 (SELECT COUNT(*) FROM diary_topics t WHERE t.scope=d.scope AND t.day=d.day) AS topic_count
FROM diary_days d

-- name: count
SELECT COUNT(*) AS total FROM ({source})
WHERE (:scope='' OR scope=:scope) AND (:kind='' OR kind=:kind)
 AND (:start='' OR day>=:start) AND (:end='' OR day<=:end)
 AND (:q='' OR instr(lower(search),lower(:q))>0)

-- name: page
SELECT * FROM ({source})
WHERE (:scope='' OR scope=:scope) AND (:kind='' OR kind=:kind)
 AND (:start='' OR day>=:start) AND (:end='' OR day<=:end)
 AND (:q='' OR instr(lower(search),lower(:q))>0)
ORDER BY {order}, scope, id LIMIT :limit OFFSET :skip

-- name: diary_topics
SELECT * FROM diary_topics WHERE scope=? AND day=? ORDER BY topic_at,id;

-- name: delete_messages
DELETE FROM messages WHERE scope=? AND id=?;

-- name: delete_decisions
DELETE FROM controller_decisions WHERE scope=? AND id=?;

-- name: delete_topics
DELETE FROM diary_topics WHERE scope=? AND id=?;

-- name: delete_diaries
DELETE FROM diary_days WHERE scope=? AND day=?;
